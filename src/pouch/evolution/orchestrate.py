"""evolve orchestration — 조각들을 잇는 얇은 planner.

순수 계획과 IO 적용을 분리한다:
  plan_evolution: usage_log → aggregate → active state → drop 후보 (순수 조립)
  apply_drop    : uninstall_entry(표면만) + mark_dropped(상태). 카탈로그 불변.

정책: 제안만. plan은 후보를 계산할 뿐 아무것도 안 내린다. apply_drop은 동의를
받은 뒤에만 CLI가 호출한다. "떨어진다 ≠ 삭제된다" — apply_drop도 카탈로그를
만지지 않는다(uninstall_entry에 위임, store.get은 read-only).
"""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.install import install_entry
from pouch.catalog.model import SURFACE_PLUGIN, alias_map
from pouch.catalog.store import CatalogStore
from pouch.catalog.uninstall import uninstall_entry
from pouch.evolution.attach import AttachCandidate, attach_candidates
from pouch.evolution.candidates import DropCandidate, EvolveConfig, drop_candidates
from pouch.evolution.compaction import compact, full_stats
from pouch.evolution.state import active_entries, mark_dropped
from pouch.evolution.summary import load_summary, save_summary
from pouch.evolution.usage_log import read_events, rewrite_events


def plan_evolution(
    *,
    now: str,
    config: EvolveConfig,
    usage_path: Path | None = None,
    state_path: Path | None = None,
    summary_path: Path | None = None,
) -> list[DropCandidate]:
    """로그·상태를 읽어 drop 후보를 계산한다. 아무것도 내리지 않는다(제안만).

    접힌 요약 + 최근 상세를 합쳐 전체 통계를 낸다 — 접기로 오래된 이벤트가
    jsonl에서 빠져도 "썼던 도구"가 never-used로 오분류되지 않게 한다.
    """
    events = read_events(log_path=usage_path)
    summary = load_summary(path=summary_path)
    stats = full_stats(summary, events)
    active = active_entries(state_path=state_path)
    return drop_candidates(active, stats, now=now, config=config)


def run_compaction(
    *,
    now: str,
    after_days: int,
    usage_path: Path | None = None,
    summary_path: Path | None = None,
) -> int:
    """경계 밖 이벤트를 요약으로 접고 로그 공간을 회수한다. 접힌 줄 수 반환.

    요약을 먼저 원자적으로 확정한 뒤 로그를 재작성한다 — 재작성이 실패해도
    compacted_through가 잔재를 무시시켜 이중 계산이 없다(멱등).
    """
    events = read_events(log_path=usage_path)
    summary = load_summary(path=summary_path)
    new_summary, recent = compact(events, summary, now=now, after_days=after_days)
    folded = len(events) - len(recent)
    if folded > 0:
        save_summary(new_summary, path=summary_path)
        rewrite_events(recent, log_path=usage_path)
    return folded


def plan_attach(
    *,
    now: str,
    store: CatalogStore,
    usage_path: Path | None = None,
    state_path: Path | None = None,
) -> list[AttachCandidate]:
    """로그·상태·카탈로그를 읽어 당겨올 후보를 계산한다. 아무것도 안 붙인다(제안만)."""
    events = read_events(log_path=usage_path)
    active = active_entries(state_path=state_path)
    entries = list(store.list())
    return attach_candidates(
        events,
        catalog_ids={entry.id for entry in entries},
        active_ids=set(active),
        now=now,
        alias_map=alias_map(entries),
        plugin_surfaced={e.id for e in entries if e.surface == SURFACE_PLUGIN},
    )


def apply_drop(
    entry_id: str,
    *,
    store: CatalogStore,
    skills_dir: Path,
    mcp_config_path: Path,
    state_path: Path | None = None,
) -> bool:
    """한 entry를 표면에서 내리고 상태를 dropped로 표시한다. 카탈로그는 불변.

    카탈로그에 엔트리가 없으면(이미 삭제 등) False. 있으면 uninstall 후 True.
    """
    entry = store.get(entry_id)
    if entry is None:
        return False
    uninstall_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config_path)
    mark_dropped(entry_id, state_path=state_path)
    return True


def apply_reattach(
    entry_id: str,
    *,
    store: CatalogStore,
    skills_dir: Path,
    mcp_config_path: Path,
    state_path: Path | None = None,
) -> bool:
    """drop됐던 entry를 표면에 다시 올린다 — 재부착 = install_entry 재실행.

    install_entry가 state를 active로 되돌리고 installed_at 시계도 리셋한다.
    카탈로그에 없으면 False(adopt 후보는 여기로 못 온다 — 편입은 import가 담당).
    """
    entry = store.get(entry_id)
    if entry is None:
        return False
    install_entry(
        entry, skills_dir=skills_dir, mcp_config_path=mcp_config_path,
        state_path=state_path,
    )
    return True
