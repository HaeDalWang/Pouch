"""`pouch` 민낯 상태 화면 — 주머니가 살아있음을 보여주는 표면.

Phase 4.6 ②: 루프(수집→집계→진화)는 다 돌아가는데 보여주는 곳이 없어서
체감이 없었다. 여기서 "뭐가 담겼고 / 최근 뭘 썼고 / 뭐가 주머니 밖인지"를
한 화면으로 모은다. 집계는 순수 함수(build_status), IO는 gather_status에 격리.
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.catalog.model import Ownership, ToolEntry
from pouch.evolution.aggregate import aggregate_usage, events_within
from pouch.evolution.usage_log import UsageEvent

_RECENT_WINDOW_DAYS = 7
_TOP_N = 3


@dataclass(frozen=True)
class PouchStatus:
    """한 화면에 담을 주머니 스냅샷."""

    memory_count: int
    catalog_total: int
    owned: int
    vendored: int
    linked: int
    active_count: int
    recent_total: int  # 최근 창 안의 총 사용 횟수
    recent_top: tuple[tuple[str, int], ...]  # (entry_id, count) 상위
    outside_pouch: tuple[str, ...]  # 최근 쓰였는데 카탈로그 밖 (attach 신호)
    hook_memory: bool
    hook_usage: bool


def build_status(
    *,
    memory_count: int,
    entries: list[ToolEntry],
    active_ids: set[str],
    events: list[UsageEvent],
    now: str,
    hook_memory: bool,
    hook_usage: bool,
) -> PouchStatus:
    """스냅샷을 계산한다(순수 — 시계·IO 없음, now는 주입)."""
    by_ownership = {o: 0 for o in Ownership}
    for entry in entries:
        by_ownership[entry.ownership] += 1

    recent = events_within(events, now=now, window_days=_RECENT_WINDOW_DAYS)
    stats = aggregate_usage(recent)
    ranked = sorted(stats.items(), key=lambda item: (-item[1].count, item[0]))
    catalog_ids = {entry.id for entry in entries}

    return PouchStatus(
        memory_count=memory_count,
        catalog_total=len(entries),
        owned=by_ownership[Ownership.OWNED],
        vendored=by_ownership[Ownership.VENDORED],
        linked=by_ownership[Ownership.LINKED],
        active_count=len(active_ids & catalog_ids),
        recent_total=len(recent),
        recent_top=tuple((eid, stat.count) for eid, stat in ranked[:_TOP_N]),
        outside_pouch=tuple(sorted(eid for eid in stats if eid not in catalog_ids)),
        hook_memory=hook_memory,
        hook_usage=hook_usage,
    )


def gather_status(*, now: str) -> PouchStatus:
    """현재 주머니 상태를 파일들에서 모은다(IO는 여기서만)."""
    from pouch import paths
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.state import active_entries
    from pouch.evolution.usage_log import read_events
    from pouch.hooks.settings import is_installed, is_usage_hook_installed, load_settings

    memory_dir = paths.global_memory_dir()
    memory_count = (
        len([p for p in memory_dir.glob("*.md") if p.name != "MEMORY.md"])
        if memory_dir.is_dir()
        else 0
    )
    settings = load_settings(paths.claude_settings_path())

    return build_status(
        memory_count=memory_count,
        entries=list(CatalogStore().list()),
        active_ids=set(active_entries()),
        events=read_events(),
        now=now,
        hook_memory=is_installed(settings),
        hook_usage=is_usage_hook_installed(settings),
    )


def render_lines(status: PouchStatus) -> list[str]:
    """스냅샷을 rich 마크업 줄들로 그린다. 비어 있으면 채우는 법을 안내한다."""
    mark = lambda on: "[green]●[/green]" if on else "[dim]○[/dim]"  # noqa: E731
    lines = ["🦦 [bold]pouch[/bold] — 주머니 상태", ""]

    if status.catalog_total == 0:
        lines.append("  📦 카탈로그가 비어 있습니다 — 담기: [cyan]pouch catalog import <경로>[/cyan]")
    else:
        lines.append(
            f"  📦 카탈로그 {status.catalog_total}개"
            f" (owned {status.owned} · vendored {status.vendored} · linked {status.linked})"
            f" — 표면에 {status.active_count}개"
        )
    lines.append(f"  🧠 기억 {status.memory_count}개")

    if status.recent_total:
        lines.append(f"  🌊 최근 {_RECENT_WINDOW_DAYS}일 사용 {status.recent_total}회")
        for entry_id, count in status.recent_top:
            lines.append(f"     • [cyan]{entry_id}[/cyan] {count}회")
    else:
        lines.append(f"  🌊 최근 {_RECENT_WINDOW_DAYS}일 사용 기록 없음")

    if status.outside_pouch:
        lines.append(
            f"  🧲 주머니 밖에서 쓰는 도구 {len(status.outside_pouch)}개"
            " — [cyan]pouch evolve[/cyan]로 확인"
        )

    lines.append(
        f"  🔌 연결: 기억 주입 {mark(status.hook_memory)} · 사용 로깅 {mark(status.hook_usage)}"
    )
    return lines
