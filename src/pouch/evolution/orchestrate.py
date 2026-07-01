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

from pouch.catalog.store import CatalogStore
from pouch.catalog.uninstall import uninstall_entry
from pouch.evolution.aggregate import aggregate_usage
from pouch.evolution.candidates import DropCandidate, EvolveConfig, drop_candidates
from pouch.evolution.state import active_entries, mark_dropped
from pouch.evolution.usage_log import read_events


def plan_evolution(
    *,
    now: str,
    config: EvolveConfig,
    usage_path: Path | None = None,
    state_path: Path | None = None,
) -> list[DropCandidate]:
    """로그·상태를 읽어 drop 후보를 계산한다. 아무것도 내리지 않는다(제안만)."""
    stats = aggregate_usage(read_events(log_path=usage_path))
    active = active_entries(state_path=state_path)
    return drop_candidates(active, stats, now=now, config=config)


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
