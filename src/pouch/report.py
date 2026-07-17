"""`pouch report` — 기간별 주머니 리포트("이번 주/달 뭘 쓰고 뭐가 닳았나").

`status`가 "지금 한 장"이라면 리포트는 그 **시간축 확장**이다. 최적화를 *보이게*
만들어(많이 쓴 것·안 쓰여 닳는 것·주머니 밖에서 쓰는 것) 사용자가 evolve로 행동하게
한다. read-only — 아무것도 안 바꾼다(TOOLKIT-OPTIMIZATION.md 후보 A, 나침반 3필터 통과).

집계는 순수 함수(build_report), IO는 gather_report에 격리. usage 집계·별칭 접기는
evolve와 같은 코어를 재사용한다(새 시스템 안 지음).
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.catalog.model import ToolEntry, alias_map
from pouch.evolution.aggregate import aggregate_usage, canonicalize_stats, events_within
from pouch.evolution.candidates import has_usage_signal
from pouch.evolution.core_tools import core_entry_ids
from pouch.evolution.learned_profile import learned_interests
from pouch.evolution.usage_log import UsageEvent

_TOP_N = 5
_LEARNED_CAP = 12  # 인식 표면이라 상위 몇 개만 — 전량은 노이즈


@dataclass(frozen=True)
class ToolkitReport:
    """한 기간의 주머니 스냅샷."""

    window_days: int
    total_uses: int  # 창 안 총 사용 횟수
    active_count: int  # 표면(연장통)에 올라온 카탈로그 도구 수
    core: tuple[str, ...]  # 지속·빈도로 손에 맞은 핵심 도구(전체 이력 기준, 창 무관)
    learned_interests: tuple[str, ...]  # 핵심 도구가 달고 온 토큰 = 실사용으로 배운 관심사(추천 참고)
    most_used: tuple[tuple[str, int], ...]  # (id, count) — 카탈로그 도구 상위
    idle_active: tuple[str, ...]  # 표면에 있는데 창 안에 안 쓰인 신호형 도구(닳는 중)
    outside_pouch: tuple[tuple[str, int], ...]  # 카탈로그 밖인데 쓴 것 (id, count)
    project_name: str | None = None  # 현재 프로젝트 이름(맥락 개인화 레인 2a)
    project_top: tuple[tuple[str, int], ...] = ()  # 이 프로젝트에서 쓴 것 중 카탈로그에 있는 것
    project_outside: tuple[tuple[str, int], ...] = ()  # 이 프로젝트에서 쓰는데 어느 주머니에도 없는 것


def build_report(
    *,
    entries: list[ToolEntry],
    active_ids: set[str],
    events: list[UsageEvent],
    now: str,
    window_days: int,
    top_n: int = _TOP_N,
    project_events: list[UsageEvent] | None = None,
    project_name: str | None = None,
    project_catalog_ids: set[str] | None = None,
) -> ToolkitReport:
    """기간 스냅샷을 계산한다(순수 — 시계·IO 없음, now는 주입).

    "닳는 중"은 신호형 도구(스킬·mcp)만 센다 — 훅·규칙·에이전트는 사용 신호가 원래
    안 찍혀 "안 씀"을 판별할 수 없기 때문(evolve의 drop 방어와 같은 정신).
    """
    aliases = alias_map(entries)
    recent = events_within(events, now=now, window_days=window_days)
    stats = canonicalize_stats(aggregate_usage(recent), aliases)
    catalog_ids = {entry.id for entry in entries}
    by_id = {entry.id: entry for entry in entries}
    used_ids = set(stats)
    # 핵심은 전체 이력(창 무관)의 지속·빈도로 — 이번 창이 조용해도 손에 맞은 도구는 핵심.
    core = tuple(sorted(core_entry_ids(events, alias_map=aliases) & catalog_ids))
    # 학습된 관심사: 핵심 도구가 달고 온 토큰(수렴 순). 실사용이 진짜 프로필을 배운다.
    learned = tuple(
        token for token, _ in learned_interests(events, entries, alias_map=aliases)
    )[:_LEARNED_CAP]

    ranked = sorted(stats.items(), key=lambda item: (-item[1].count, item[0]))
    most_used = tuple(
        (eid, stat.count) for eid, stat in ranked if eid in catalog_ids
    )[:top_n]
    outside_pouch = tuple(
        (eid, stat.count) for eid, stat in ranked if eid not in catalog_ids
    )
    idle_active = tuple(
        sorted(
            eid
            for eid in active_ids
            if eid in catalog_ids and eid not in used_ids and has_usage_signal(by_id[eid])
        )
    )

    # 맥락(레인 2a): 프로젝트 로컬 로그를 "주머니 안(등록된 것)"과 "주머니 밖(담을 후보)"
    # 으로 가른다 — 전역 리포트(most_used/outside)와 같은 구조. 아는 것 = 전역 ∪ 프로젝트 카탈로그.
    project_top: tuple[tuple[str, int], ...] = ()
    project_outside: tuple[tuple[str, int], ...] = ()
    if project_events:
        known = catalog_ids | (project_catalog_ids or set())
        p_recent = events_within(project_events, now=now, window_days=window_days)
        p_stats = canonicalize_stats(aggregate_usage(p_recent), aliases)
        p_ranked = sorted(p_stats.items(), key=lambda item: (-item[1].count, item[0]))
        project_top = tuple((eid, stat.count) for eid, stat in p_ranked if eid in known)[:top_n]
        project_outside = tuple(
            (eid, stat.count) for eid, stat in p_ranked if eid not in known
        )[:top_n]

    return ToolkitReport(
        window_days=window_days,
        total_uses=len(recent),
        active_count=len(active_ids & catalog_ids),
        core=core,
        learned_interests=learned,
        most_used=most_used,
        idle_active=idle_active,
        outside_pouch=outside_pouch,
        project_name=project_name,
        project_top=project_top,
        project_outside=project_outside,
    )


def gather_report(*, now: str, window_days: int) -> ToolkitReport:
    """현재 주머니를 파일들에서 모은다(IO는 여기서만)."""
    from pouch import paths
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.state import active_entries
    from pouch.evolution.usage_log import read_events

    # 맥락(레인 2a·P3): 프로젝트 안이면 그 repo의 로컬 사용 로그·카탈로그도 읽는다(로컬 전용).
    root = paths.find_project_root()
    project_events = read_events(log_path=root / ".pouch" / "usage.jsonl") if root else []
    project_catalog_ids = (
        {e.id for e in CatalogStore(catalog_dir=root / ".pouch" / "catalog").list()}
        if root
        else set()
    )

    return build_report(
        entries=list(CatalogStore().list()),
        active_ids=set(active_entries()),
        events=read_events(),
        now=now,
        window_days=window_days,
        project_events=project_events,
        project_name=root.name if root else None,
        project_catalog_ids=project_catalog_ids,
    )


def render_report_lines(report: ToolkitReport) -> list[str]:
    """스냅샷을 rich 마크업 줄들로 그린다."""
    lines = [f"🦦 [bold]pouch 리포트[/bold] — 최근 {report.window_days}일", ""]

    # 핵심 도구는 전체 이력 기준이라, 이번 창이 조용해도 맨 위에 먼저 보인다.
    if report.core:
        lines.append(f"  🪨 [bold]핵심 도구[/bold] {len(report.core)}개 — 손에 맞은(정리에서 보호)")
        for entry_id in report.core:
            lines.append(f"     • [cyan]{entry_id}[/cyan]")
        lines.append("")

    # 학습된 관심사 — 핵심 도구가 달고 온 토큰. init 답변만이 아니라 실사용이 프로필을
    # 배운다(recognition). 추천(set 매칭)이 이걸 참고한다.
    if report.learned_interests:
        joined = ", ".join(report.learned_interests)
        lines.append(f"  🧭 [bold]실사용으로 배운 관심사[/bold] — {joined}")
        lines.append("     [dim]손에 맞은 도구가 달고 온 것 · 추천이 이걸 참고합니다[/dim]")
        lines.append("")

    if report.total_uses == 0:
        lines.append("  이 기간엔 사용 기록이 없습니다.")
        lines.append("  기간을 넓혀보세요: [cyan]pouch report --days 30[/cyan]")
        return lines

    lines.append(f"  🌊 총 사용 {report.total_uses}회 · 표면 도구 {report.active_count}개")

    if report.most_used:
        lines.append("\n  [bold]많이 쓴 것[/bold]")
        for entry_id, count in report.most_used:
            lines.append(f"     • [cyan]{entry_id}[/cyan] {count}회")

    if report.idle_active:
        lines.append(
            f"\n  [bold]안 쓰여 닳는 중[/bold] {len(report.idle_active)}개"
            " — [cyan]pouch evolve[/cyan]로 정리 제안받기"
        )
        for entry_id in report.idle_active:
            lines.append(f"     • [dim]{entry_id}[/dim]")

    if report.outside_pouch:
        lines.append(
            f"\n  🧲 [bold]주머니 밖에서 쓰는 것[/bold] {len(report.outside_pouch)}개"
            " — [cyan]pouch evolve[/cyan]로 편입 안내"
        )
        for entry_id, count in report.outside_pouch:
            lines.append(f"     • [cyan]{entry_id}[/cyan] {count}회")

    if report.project_top:
        label = report.project_name or "이 프로젝트"
        lines.append(f"\n  📁 [bold]{label}[/bold]에서 많이 쓴 것 (로컬 전용)")
        for entry_id, count in report.project_top:
            lines.append(f"     • [cyan]{entry_id}[/cyan] {count}회")

    if report.project_outside:
        lines.append(
            f"\n  📁 이 프로젝트에서 쓰는데 주머니 밖 {len(report.project_outside)}개"
            " — [cyan]pouch catalog import --project[/cyan]로 담기"
        )
        for entry_id, count in report.project_outside:
            lines.append(f"     • [cyan]{entry_id}[/cyan] {count}회")

    return lines
