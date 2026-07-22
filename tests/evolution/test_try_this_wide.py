"""'이거 써봐' 넓히기 — 기준은 잘 쓰는 도구, 후보는 대기실(소스)까지.

배승도 락(2026-07-22): "472개는 잘쓰는도구 항목이 아니라 애초에 비교하기 위한
대상군 항목에 넣는다. 뮤직앱에 스마트셔플 기능 같은 거 만드는 중인데, 기존에는
내가 이미 듣고싶은 거 자주 듣는 플레이리스트 만든 것에서만 가져왔는데 그게 아니라
애초에 전체 음원 중에서 찾아서 넣도록"

고치는 두 겹:
  ① 기준 도구 — "썼는데 표면에 없는 것"(구조적으로 공집합: 쓰려면 표면에 있어야
    한다)에서 "반복해서 쓰는 것"으로. 표면에 있든 없든 상관 없다.
  ② 후보 풀 — 카탈로그(9)만이 아니라 소스 대기실(472)까지. 대기실도 sweep이
    실측한 "이미 깔린 것"이라 지어내기 금지 원칙 안이다(바깥 마켓은 여전히 raft 뒤).
"""

from __future__ import annotations

from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.evolution.aggregate import UsageStat
from pouch.evolution.similar import frequent_tool_ids
from pouch.evolution.orchestrate import plan_try_this_from_usage
from pouch.evolution.usage_log import UsageEvent, append_event


def _stat(count: int, last: str = "2026-07-22T10:00:00") -> UsageStat:
    return UsageStat(count=count, last_used=last)


# --- ① 기준 도구: 반복해서 쓰는 것 ---


def test_frequent_tools_are_ranked_by_count() -> None:
    stats = {"a": _stat(3), "b": _stat(9), "c": _stat(5)}

    assert frequent_tool_ids(stats) == ["b", "c", "a"]


def test_a_single_use_is_not_a_habit() -> None:
    """반복이 증거다 — 1회는 우연일 수 있어 기준이 못 된다."""
    stats = {"once": _stat(1), "twice": _stat(2)}

    assert frequent_tool_ids(stats) == ["twice"]


def test_ties_break_deterministically_by_id() -> None:
    stats = {"zeta": _stat(4), "alpha": _stat(4)}

    assert frequent_tool_ids(stats) == ["alpha", "zeta"]


def test_no_usage_means_no_anchors() -> None:
    assert frequent_tool_ids({}) == []


# --- ② 후보 풀: 대기실까지 ---


def _skill(entry_id: str, description: str) -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id, kind=ToolKind.SKILL, source="test",
        title=entry_id, description=description, body="본문",
    )


def _use(entry_id: str, times: int, log_path) -> None:
    for _ in range(times):
        append_event(
            UsageEvent(entry_id=entry_id, ts="2026-07-22T09:00:00"), log_path=log_path
        )


def test_an_active_well_used_tool_gets_suggestions_from_the_staging_area(
    tmp_path,
) -> None:
    """핵심 시나리오 — 잘 쓰는(표면에 올라간) 도구 곁에 대기실의 비슷한 것이 뜬다.

    옛 조건("표면에 없는 것만 기준")에선 이 배치가 구조적으로 0건이었다.
    """
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    sources = CatalogStore(catalog_dir=tmp_path / "sources")
    log = tmp_path / "usage.jsonl"
    catalog.save(_skill("terraform", "terraform infrastructure deploy cloud"))
    sources.save(_skill("pulumi", "pulumi infrastructure deploy cloud"))
    _use("terraform", 5, log)

    plans = plan_try_this_from_usage(
        store=catalog, source_store=sources,
        usage_path=log, state_path=tmp_path / "state.json",
        active_ids={"terraform"},  # 표면에 올라가 있어도 기준이 된다
    )

    assert [p.anchor_id for p in plans] == ["terraform"]
    assert "pulumi" in [c.entry.id for c in plans[0].similar]


def test_a_staged_copy_of_a_catalog_entry_does_not_double_up(tmp_path) -> None:
    """같은 도구가 카탈로그와 대기실에 다 있으면 카탈로그 것만(개인화 태그가 붙는 쪽)."""
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    sources = CatalogStore(catalog_dir=tmp_path / "sources")
    log = tmp_path / "usage.jsonl"
    catalog.save(_skill("terraform", "terraform infrastructure deploy"))
    catalog.save(_skill("pulumi", "pulumi infrastructure deploy"))
    sources.save(_skill("pulumi", "pulumi infrastructure deploy"))
    _use("terraform", 3, log)

    plans = plan_try_this_from_usage(
        store=catalog, source_store=sources,
        usage_path=log, state_path=tmp_path / "state.json", active_ids=set(),
    )

    ids = [c.entry.id for p in plans for c in p.similar]
    assert ids.count("pulumi") == 1


def test_noisy_screens_are_capped_to_a_few_anchors(tmp_path) -> None:
    """보여줄 게 있는 기준 도구가 많아도 상위 몇 개까지만(잔소리 방어).

    조용한 기준(비슷한 게 없는 것)은 자릿수를 안 먹는다 — 캡은 입구가 아니라
    출구에 건다.
    """
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    sources = CatalogStore(catalog_dir=tmp_path / "sources")
    log = tmp_path / "usage.jsonl"
    # 시끄러운 기준 4개(각각 비슷한 후보 보유) + 제일 많이 쓴 조용한 기준 1개
    for i, name in enumerate(("aa", "bb", "cc", "dd")):
        catalog.save(_skill(name, f"{name} shared topic infrastructure deploy"))
        sources.save(_skill(f"{name}-alike", f"{name} shared topic infrastructure deploy"))
        _use(name, 8 - i, log)
    catalog.save(_skill("quiet", "완전히 다른 얘기"))
    _use("quiet", 20, log)

    plans = plan_try_this_from_usage(
        store=catalog, source_store=sources,
        usage_path=log, state_path=tmp_path / "state.json", active_ids=set(),
    )

    assert len(plans) == 3  # 출구 캡
    assert [p.anchor_id for p in plans] == ["aa", "bb", "cc"]  # 많이 쓴 순
