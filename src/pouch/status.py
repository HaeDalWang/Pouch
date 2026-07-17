"""`pouch` 민낯 상태 화면 — 주머니가 살아있음을 보여주는 표면.

Phase 4.6 ②: 루프(수집→집계→진화)는 다 돌아가는데 보여주는 곳이 없어서
체감이 없었다. 여기서 "뭐가 담겼고 / 최근 뭘 썼고 / 뭐가 주머니 밖인지"를
한 화면으로 모은다. 집계는 순수 함수(build_status), IO는 gather_status에 격리.
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.catalog.model import Ownership, ToolEntry, alias_map
from pouch.evolution.aggregate import aggregate_usage, canonicalize_stats, events_within
from pouch.evolution.core_tools import core_entry_ids
from pouch.evolution.learned_profile import learned_interests
from pouch.evolution.usage_log import UsageEvent

_RECENT_WINDOW_DAYS = 7
_TOP_N = 3
_MEM_PREVIEW_N = 3
_LEARNED_TOP_N = 6  # 민낯 화면은 좁으니 상위 몇 개만


@dataclass(frozen=True)
class HostLink:
    """한 에이전트(호스트)의 연결 상태 한 줄.

    usage가 None이면 파일 호스트(Kiro 부류) — 도구 사용 로깅을 못 하므로
    화면에서 "—"로 정직하게 비운다. 훅 호스트는 True/False로 켜짐 여부를 담는다.
    """

    display_name: str
    memory: bool
    usage: bool | None


@dataclass(frozen=True)
class PouchStatus:
    """한 화면에 담을 주머니 스냅샷."""

    version: str  # pouch 버전
    revision: str | None  # git 체크아웃이면 "<커밋> · <날짜>", 설치본이면 None
    memory_count: int
    memory_preview: tuple[str, ...]  # 기억 몇 개의 한 줄 요약(전역 기억)
    catalog_total: int
    owned: int
    vendored: int
    linked: int
    staged_count: int  # 소스에 재워뒀지만 아직 카탈로그로 진입 안 한 것(가리키기만 한 것)
    active_count: int
    core_count: int  # 지속·빈도로 손에 맞은 핵심 도구 수(전체 이력 기준)
    learned_interests: tuple[str, ...]  # 핵심 도구가 달고 온 토큰 = 실사용으로 배운 관심사
    recent_total: int  # 최근 창 안의 총 사용 횟수
    recent_top: tuple[tuple[str, int], ...]  # (entry_id, count) 상위
    outside_pouch: tuple[str, ...]  # 최근 쓰였는데 카탈로그 밖 (attach 신호)
    hosts: tuple[HostLink, ...]  # 이 머신에서 감지된 에이전트별 연결 상태


def build_status(
    *,
    entries: list[ToolEntry],
    active_ids: set[str],
    events: list[UsageEvent],
    now: str,
    version: str = "",
    revision: str | None = None,
    memory_count: int = 0,
    memory_preview: tuple[str, ...] = (),
    staged_count: int = 0,
    hosts: tuple[HostLink, ...] = (),
) -> PouchStatus:
    """스냅샷을 계산한다(순수 — 시계·IO 없음, now·hosts·기억 요약은 주입)."""
    by_ownership = {o: 0 for o in Ownership}
    for entry in entries:
        by_ownership[entry.ownership] += 1

    aliases = alias_map(entries)
    recent = events_within(events, now=now, window_days=_RECENT_WINDOW_DAYS)
    # 런타임 별칭(plugin_<플러그인>_<서버>)을 카탈로그 정식 id로 접어 비교한다.
    stats = canonicalize_stats(aggregate_usage(recent), aliases)
    ranked = sorted(stats.items(), key=lambda item: (-item[1].count, item[0]))
    catalog_ids = {entry.id for entry in entries}
    # 핵심 도구는 전체 이력 기준(최근 창 아님) — 조용한 주에도 손에 맞은 건 핵심.
    core = core_entry_ids(events, alias_map=aliases) & catalog_ids
    # 학습된 관심사: 핵심 도구가 달고 온 토큰(수렴 순) — 실사용이 배운 프로필.
    learned = tuple(
        token for token, _ in learned_interests(events, entries, alias_map=aliases)
    )[:_LEARNED_TOP_N]

    return PouchStatus(
        version=version,
        revision=revision,
        memory_count=memory_count,
        memory_preview=memory_preview,
        catalog_total=len(entries),
        owned=by_ownership[Ownership.OWNED],
        vendored=by_ownership[Ownership.VENDORED],
        linked=by_ownership[Ownership.LINKED],
        staged_count=staged_count,
        active_count=len(active_ids & catalog_ids),
        core_count=len(core),
        learned_interests=learned,
        recent_total=len(recent),
        recent_top=tuple((eid, stat.count) for eid, stat in ranked[:_TOP_N]),
        outside_pouch=tuple(sorted(eid for eid in stats if eid not in catalog_ids)),
        hosts=hosts,
    )


def _detect_hosts() -> tuple[HostLink, ...]:
    """이 머신에서 감지된 에이전트별 연결 상태를 모은다(IO).

    훅 호스트(Claude·Codex)는 설정 디렉토리가 있으면 대상 — 첫 연결 전에도 잡혀
    "감지됐지만 아직 연결 안 됨(○)"이 보인다. 파일 호스트(Kiro)는 전역 설치 신호로
    잡고, 사용 로깅이 불가하므로 usage=None으로 표시한다.
    """
    from pouch.hosts.registry import detect_file_supported, detect_hook_installed

    links: list[HostLink] = []
    for adapter in detect_hook_installed():
        config = adapter.load(adapter.config_path())
        links.append(
            HostLink(
                display_name=adapter.display_name,
                memory=adapter.is_memory_installed(config),
                usage=adapter.is_usage_installed(config),
            )
        )
    for file_adapter in detect_file_supported():
        links.append(
            HostLink(
                display_name=file_adapter.display_name,
                memory=file_adapter.is_linked(),
                usage=None,
            )
        )
    return tuple(links)


def _git_revision() -> str | None:
    """이 소스가 git 체크아웃이면 "<커밋> · <날짜>"를, 아니면 None.

    개발 중(에디터블 설치)엔 자기 레포에서 잡히고, pip 설치본엔 git이 없어 None →
    헤더는 버전만 보인다(설치본 대비 graceful). 2초 타임아웃으로 멈춤을 막는다.
    """
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]  # src/pouch/status.py → 레포 루트
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo), "log", "-1", "--format=%h · %cd", "--date=short"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def _memory_preview(limit: int) -> tuple[str, ...]:
    """전역 기억의 한 줄 요약 몇 개(description). pouch가 무엇을 기억하는지 맛보기."""
    from pouch.memory.model import MemoryScope
    from pouch.memory.store import MemoryStore

    previews = [
        entry.description.strip()
        for entry in MemoryStore().list()
        if entry.scope is MemoryScope.GLOBAL and entry.description.strip()
    ]
    return tuple(previews[:limit])


def gather_status(*, now: str) -> PouchStatus:
    """현재 주머니 상태를 파일들에서 모은다(IO는 여기서만)."""
    from pouch import __version__, paths
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.state import active_entries
    from pouch.evolution.usage_log import read_events

    memory_dir = paths.global_memory_dir()
    memory_count = (
        len([p for p in memory_dir.glob("*.md") if p.name != "MEMORY.md"])
        if memory_dir.is_dir()
        else 0
    )
    sources_dir = paths.sources_dir()
    staged_count = len(list(sources_dir.glob("*.md"))) if sources_dir.is_dir() else 0

    return build_status(
        version=__version__,
        revision=_git_revision(),
        memory_count=memory_count,
        memory_preview=_memory_preview(_MEM_PREVIEW_N),
        staged_count=staged_count,
        entries=list(CatalogStore().list()),
        active_ids=set(active_entries()),
        events=read_events(),
        now=now,
        hosts=_detect_hosts(),
    )


# 왼쪽 라벨 컬럼 폭 — 이모지 대신 정렬된 라벨로 구획을 나눈다(otter만 남김).
_LABEL_W = 6
_INDENT = "     "  # 라벨 아래 딸림 줄(기억 미리보기·호스트 목록)의 들여쓰기


def render_lines(status: PouchStatus) -> list[str]:
    """스냅샷을 rich 마크업 줄들로 그린다. 비어 있으면 채우는 법을 안내한다."""
    lines = _render_header(status)
    lines.extend(_render_pouch(status))
    lines.extend(_render_recent(status))
    lines.extend(_render_hosts(status.hosts))
    return lines


def _label(text: str) -> str:
    """왼쪽 라벨 컬럼(정렬)."""
    return f"  [dim]{text.ljust(_LABEL_W)}[/dim]"


def _render_header(status: PouchStatus) -> list[str]:
    """otter + 버전 한 줄. git 체크아웃이면 커밋·날짜를 뒤에 붙인다(설치본은 버전만)."""
    head = f"🦦 [bold]pouch[/bold] [cyan]{status.version}[/cyan]"
    if status.revision:
        head += f"  [dim]{status.revision}[/dim]"
    return [head, ""]


def _render_pouch(status: PouchStatus) -> list[str]:
    """담긴 것 — 카탈로그 한 줄 + 기억 수, 그 아래 기억 미리보기 몇 줄."""
    if status.catalog_total == 0:
        catalog_line = (
            f"{_label('담긴 것')}카탈로그 비어 있음"
            " — [cyan]pouch catalog import <경로>[/cyan]"
        )
    else:
        catalog_line = (
            f"{_label('담긴 것')}카탈로그 {status.catalog_total}"
            f" ([dim]owned {status.owned} · vendored {status.vendored}"
            f" · linked {status.linked}[/dim] · 표면 {status.active_count})"
        )
    lines = [catalog_line]
    if status.staged_count:
        lines.append(
            f"  {_INDENT}[dim]+ 소스 {status.staged_count}개 대기[/dim]"
            "  → [cyan]pouch catalog list --sources[/cyan]"
        )
    if status.core_count:
        lines.append(
            f"  {_INDENT}[dim]핵심 도구 {status.core_count}개 — 손에 맞아 정리에서 보호[/dim]"
        )
    if status.learned_interests:
        joined = ", ".join(status.learned_interests)
        lines.append(f"  {_INDENT}[dim]배운 관심사: {joined}[/dim]")
    lines.append(f"{_label('기억')}{status.memory_count}개")
    for preview in status.memory_preview:
        lines.append(f"  {_INDENT}[dim]•[/dim] {preview}")
    return lines


def _render_recent(status: PouchStatus) -> list[str]:
    """최근 사용 — 총계와 top을 한 줄로 접는다. 주머니 밖 신호는 별도 한 줄."""
    if status.recent_total:
        top = " · ".join(
            f"[cyan]{entry_id}[/cyan] {count}" for entry_id, count in status.recent_top
        )
        line = f"{_label(f'최근 {_RECENT_WINDOW_DAYS}일')}{status.recent_total}회 — {top}"
    else:
        line = f"{_label(f'최근 {_RECENT_WINDOW_DAYS}일')}사용 기록 없음"
    lines = ["", line]

    if status.outside_pouch:
        lines.append(
            f"  {_INDENT}주머니 밖 {len(status.outside_pouch)}개"
            "  → [cyan]pouch evolve[/cyan]"
        )
    return lines


def _render_hosts(hosts: tuple[HostLink, ...]) -> list[str]:
    """감지된 에이전트별 연결 상태 블록. 파일 호스트의 사용 로깅은 '—'로 비운다."""
    if not hosts:
        return ["", f"{_label('연결')}감지된 에이전트 없음 — [cyan]pouch hook install[/cyan]"]

    mark = lambda on: "[green]●[/green]" if on else "[dim]○[/dim]"  # noqa: E731
    width = max(len(h.display_name) for h in hosts)
    lines = ["", "  [dim]연결[/dim]"]  # 딸림 줄만 있는 헤더 — 패딩 없이(자투리 공백 방지)
    for host in hosts:
        name = host.display_name.ljust(width)
        usage = "[dim]—[/dim]" if host.usage is None else mark(host.usage)
        lines.append(f"  {_INDENT}{name}   기억 {mark(host.memory)}  사용 {usage}")
    return lines
