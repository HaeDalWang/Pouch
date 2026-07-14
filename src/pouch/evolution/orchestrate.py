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

from pouch.catalog.demote import demote
from pouch.catalog.install import install_entry
from pouch.catalog.model import SURFACE_PLUGIN, alias_map
from pouch.catalog.promote import promote
from pouch.catalog.store import CatalogStore
from pouch.catalog.uninstall import uninstall_entry
from pouch.evolution.advice import Advice, plan_advice
from pouch.evolution.aggregate import canonicalize_stats
from pouch.evolution.attach import AttachCandidate, attach_candidates
from pouch.evolution.candidates import (
    DropCandidate,
    EvolveConfig,
    drop_candidates,
    has_usage_signal,
)
from pouch.evolution.compaction import compact, full_stats
from pouch.evolution.reconcile import demote_candidates, promote_candidates
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


def plan_plugin_advice(
    *,
    now: str,
    store: CatalogStore,
    config: EvolveConfig,
    usage_path: Path | None = None,
    summary_path: Path | None = None,
) -> list[Advice]:
    """plugin 도구의 관측 사용을 진화 조언으로 계산한다(제안만, 아무것도 안 바꿈).

    (A→B) 조언 경로. 통계는 canonicalize를 거친다 — 런타임 별칭(plugin_<플러그인>_
    <서버>)을 카탈로그 정식 id로 접어야 조언이 항목에 닿는다. alias가 안 걸린 도구
    (예: skill로 잘못 들어온 exa)는 여기서 조언에 안 잡힌다 — 그건 import 경로의
    문제(조각 3)라 이 조언 로직으로는 못 고친다. (1)/(3) 분리가 이 canonicalize에서 갈린다.
    """
    events = read_events(log_path=usage_path)
    summary = load_summary(path=summary_path)
    entries = list(store.list())
    stats = canonicalize_stats(full_stats(summary, events), alias_map(entries))
    return plan_advice(entries, stats, now=now, stale_days=config.stale_days)


def reconcile(
    *,
    source_store: CatalogStore,
    catalog_store: CatalogStore,
    usage_path: Path | None = None,
    summary_path: Path | None = None,
) -> list[str]:
    """실사용을 소스→카탈로그 진입으로 적용한다(관문 (다)의 실사용 트리거).

    import가 소스에만 재워둔 도구를 사용자가 실제로 쓰면 카탈로그로 진입시킨다.
    별칭 접기는 카탈로그·소스 양쪽 엔트리로 만든다 — usage는 런타임 별칭
    (plugin_<플러그인>_<도구>)으로 찍히는데 소스 id는 정식 id라, 안 접으면
    안 맞아 진입이 안 걸린다. full_stats로 접힌 옛 사용도 인정한다(단조 진입).

    진입한 id 목록을 반환한다(무엇이 새로 담겼는지 보고용).
    """
    events = read_events(log_path=usage_path)
    summary = load_summary(path=summary_path)
    source_entries = list(source_store.list())
    catalog_entries = list(catalog_store.list())
    mapping = alias_map(source_entries + catalog_entries)
    stats = canonicalize_stats(full_stats(summary, events), mapping)

    candidates = promote_candidates(
        stats,
        source_ids={e.id for e in source_entries},
        catalog_ids={e.id for e in catalog_entries},
    )
    promoted: list[str] = []
    for entry_id in candidates:
        if promote(entry_id, source_store=source_store, catalog_store=catalog_store):
            promoted.append(entry_id)
    return promoted


def migrate(
    *,
    source_store: CatalogStore,
    catalog_store: CatalogStore,
    usage_path: Path | None = None,
    summary_path: Path | None = None,
) -> list[str]:
    """안 쓰는 카탈로그 도구를 소스로 강등한다(reconcile의 거울상).

    옛 import가 실사용과 무관하게 카탈로그에 직행시킨 잉여(194)를 관문 뒤 소스로
    되돌리는 통로. 두 방어를 여기서 건다:

    canonicalize — usage는 런타임 별칭(plugin_<플러그인>_<도구>)으로 찍히는데
    카탈로그 id는 정식 id라, 안 접으면 "exa를 썼다"가 카탈로그 exa에 안 닿아
    쓰던 도구를 잘못 강등한다. reconcile과 같은 alias_map·full_stats를 쓴다.

    has_usage_signal — demote_candidates는 "카탈로그에 있고 stats에 없음"을 다
    고르는데, 훅·규칙·에이전트는 신호가 아예 안 찍혀 항상 "안 씀"으로 보인다.
    이들을 강등하면 안 되므로(신호 없음 ≠ 안 쓰임) 신호 종류만 남긴다(drop과 같은
    방어). 순수 선택엔 카탈로그 엔트리가 없어 판별 못 하니 IO를 쥔 여기서 건다.

    강등한 id 목록을 반환한다(무엇이 내려갔는지 보고용).
    """
    events = read_events(log_path=usage_path)
    summary = load_summary(path=summary_path)
    catalog_entries = list(catalog_store.list())
    source_entries = list(source_store.list())
    mapping = alias_map(source_entries + catalog_entries)
    stats = canonicalize_stats(full_stats(summary, events), mapping)

    signal_ids = {e.id for e in catalog_entries if has_usage_signal(e)}
    candidates = demote_candidates(stats, catalog_ids=signal_ids)
    demoted: list[str] = []
    for entry_id in candidates:
        if demote(entry_id, source_store=source_store, catalog_store=catalog_store):
            demoted.append(entry_id)
    return demoted


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
