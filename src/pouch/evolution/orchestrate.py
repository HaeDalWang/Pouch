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
from pouch.evolution.similar import TryThis, frequent_tool_ids, plan_try_this
from pouch.evolution.state import active_entries, mark_dropped
from pouch.evolution.summary import load_summary, save_summary
from pouch.evolution.usage_log import read_events, rewrite_events

# '이거 써봐' 화면 캡 — 보여줄 게 있는 기준 도구 상위 몇 개까지(잔소리 방어).
# 입구(기준 선정)가 아니라 출구(렌더)에 건다: 조용한 기준(비슷한 게 없는 것)은
# 자릿수를 안 먹으므로, 캡을 입구에 걸면 조용한 것들이 자리를 다 차지해
# 정작 보여줄 게 있는 기준이 밀려나는 역전이 생긴다.
_TRY_THIS_MAX_ANCHORS = 3


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


def plan_try_this_from_usage(
    *,
    store: CatalogStore,
    source_store: CatalogStore | None = None,
    repo_index_root: Path | None = None,
    usage_path: Path | None = None,
    summary_path: Path | None = None,
    state_path: Path | None = None,
    active_ids: set[str] | None = None,
    max_anchors: int = _TRY_THIS_MAX_ANCHORS,
) -> list[TryThis]:
    """잘 쓰는 도구를 기준으로 카탈로그+대기실(소스)에서 비슷한 후보를 계산한다.

    '이거 써봐' 넓히기(배승도 락 2026-07-22): "472개는 잘쓰는도구 항목이 아니라
    애초에 비교하기 위한 대상군 항목에 넣는다 … 기존에는 플레이리스트에서만
    가져왔는데 전체 음원 중에서 찾도록". 두 겹을 함께 편다:

      기준(①) — attach 후보(썼는데 표면에 없는 것)가 아니라 반복 사용 통계.
        옛 조건은 구조적 공집합이었다(쓰려면 표면에 있어야 하니까).
      풀(②) — 카탈로그 + 소스 대기실. 대기실도 sweep이 실측한 "이미 깔린 것"이라
        지어내기 금지 원칙 안이다(바깥 마켓은 여전히 raft 뒤). 같은 id가 양쪽에
        있으면 카탈로그가 이긴다(개인화 태그가 붙는 쪽).

    제안만 — 아무것도 설치·진입시키지 않는다. 통계는 요약+최근을 합쳐(습관 보존)
    canonicalize를 거친다(별칭이 접혀야 같은 도구가 안 흩어진다).
    """
    events = read_events(log_path=usage_path)
    summary = load_summary(path=summary_path)
    entries = list(store.list())
    stats = canonicalize_stats(full_stats(summary, events), alias_map(entries))
    anchors = frequent_tool_ids(stats)
    if not anchors:
        return []

    sources = source_store or CatalogStore(catalog_dir=_sources_dir())
    catalog_ids = {e.id for e in entries}
    staged = [e for e in sources.list() if e.id not in catalog_ids]

    # 풀의 다음 겹(조각 ③): 등록한 저장소의 색인. 정체가 `<저장소>/<도구>`라 출처가
    # 이름에 실려 다닌다. 이미 아는 도구(카탈로그·대기실)의 저장소 사본은 뺀다 —
    # 같은 걸 두 번 권하는 소음 방지(카탈로그가 이기는 기존 원칙의 연장).
    from pouch.repos.index import indexed_entries

    known = catalog_ids | {e.id for e in staged}
    from_repos = [
        e
        for e in indexed_entries(repo_index_root or _repo_index_root())
        if e.id.split("/", 1)[1] not in known
    ]

    active = active_ids if active_ids is not None else set(active_entries(state_path=state_path))
    plans = plan_try_this(anchors, entries + staged + from_repos, active_ids=active)
    return plans[:max_anchors]


def _sources_dir() -> Path:
    from pouch import paths

    return paths.sources_dir()


def _repo_index_root() -> Path:
    from pouch import paths

    return paths.repo_index_root()


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


def plan_migrate(
    *,
    catalog_store: CatalogStore,
    source_store: CatalogStore,
    usage_path: Path | None = None,
    summary_path: Path | None = None,
) -> list[str]:
    """강등할 후보 id를 계산한다. 아무것도 안 옮긴다(읽기전용 계획).

    migrate의 적용 없는 짝 — dry-run 미리보기와 백업 전 목록이 이 단일 출처를
    본다(plan_evolution/apply_drop 분리와 같은 정신). 두 방어를 여기서 건다:

    canonicalize — usage는 런타임 별칭(plugin_<플러그인>_<도구>)으로 찍히는데
    카탈로그 id는 정식 id라, 안 접으면 "exa를 썼다"가 카탈로그 exa에 안 닿아
    쓰던 도구를 잘못 강등한다. reconcile과 같은 alias_map·full_stats를 쓴다.

    has_usage_signal — demote_candidates는 "카탈로그에 있고 stats에 없음"을 다
    고르는데, 훅·규칙·에이전트는 신호가 아예 안 찍혀 항상 "안 씀"으로 보인다.
    이들을 강등하면 안 되므로(신호 없음 ≠ 안 쓰임) 신호 종류만 남긴다(drop과 같은
    방어). 순수 선택엔 카탈로그 엔트리가 없어 판별 못 하니 IO를 쥔 여기서 건다.
    """
    events = read_events(log_path=usage_path)
    summary = load_summary(path=summary_path)
    catalog_entries = list(catalog_store.list())
    source_entries = list(source_store.list())
    mapping = alias_map(source_entries + catalog_entries)
    stats = canonicalize_stats(full_stats(summary, events), mapping)

    signal_ids = {e.id for e in catalog_entries if has_usage_signal(e)}
    return demote_candidates(stats, catalog_ids=signal_ids)


def migrate(
    *,
    source_store: CatalogStore,
    catalog_store: CatalogStore,
    usage_path: Path | None = None,
    summary_path: Path | None = None,
) -> list[str]:
    """안 쓰는 카탈로그 도구를 소스로 강등한다(reconcile의 거울상).

    옛 import가 실사용과 무관하게 카탈로그에 직행시킨 잉여(194)를 관문 뒤 소스로
    되돌리는 통로. 후보 계산은 plan_migrate에 위임하고(단일 출처) 여기선 적용만 한다.

    강등한 id 목록을 반환한다(무엇이 내려갔는지 보고용).
    """
    candidates = plan_migrate(
        catalog_store=catalog_store, source_store=source_store,
        usage_path=usage_path, summary_path=summary_path,
    )
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
