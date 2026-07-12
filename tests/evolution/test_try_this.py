"""'이거 써봐' 조립 계약 검증 — 반복 앵커마다 풀에서 비슷한 후보를 붙인다.

정책([[pouch-try-this-recommend-policy]] 조각 3): adopt/reattach(반복 신호)가 뜰 때
"비슷한 후보도 이거"를 같이 보여준다. 새 파이프 안 만듦 — 순수 조립(풀+비슷)만
하고, 렌더·통로는 기존 것 재사용.

정직한 균일 처리: 앵커를 종류로 특별 취급하지 않는다. reattach 앵커는 풀 안이라
비슷한 게 붙고, adopt 앵커는 풀 밖이라 날것 예외로 빈 결과 → 조용히 빠진다
(하드코딩 없이 메커니즘이 처리).

  ① 풀 안 앵커(reattach) → 비슷한 후보 붙음
  ② 풀 밖 앵커(adopt) → 조용히 빠짐(결과에 없음)
  ③ 비슷한 게 없는 앵커 → 조용히 빠짐(소음 0)
  ④ active·앵커 자신은 이미 find_similar가 제외(위임)
  ⑤ 순수 함수
"""

from __future__ import annotations

from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.evolution.similar import TryThis, plan_try_this


def _entry(id: str, *tags: str) -> ToolEntry:
    return ToolEntry.vendored(
        id=id, kind=ToolKind.SKILL, source="s", title=id, description=f"{id} 설명",
        upstream="/up", synced_at="2026-01-01", overlay=Overlay(tags=tuple(tags)),
    )


def test_contract1_in_pool_anchor_gets_similar() -> None:
    entries = [_entry("terraform", "iac"), _entry("pulumi", "iac"), _entry("cdk", "iac")]

    result = plan_try_this(["terraform"], entries, active_ids=set())

    assert len(result) == 1
    assert isinstance(result[0], TryThis)
    assert result[0].anchor_id == "terraform"
    assert {c.entry.id for c in result[0].similar} == {"pulumi", "cdk"}


def test_contract2_out_of_pool_anchor_drops_silently() -> None:
    # adopt 앵커(카탈로그 밖) → 풀에 없음 → 날것 예외 → 결과에서 조용히 빠짐
    entries = [_entry("pulumi", "iac"), _entry("cdk", "iac")]

    result = plan_try_this(["external-tool"], entries, active_ids=set())

    assert result == []


def test_contract3_anchor_without_similars_drops() -> None:
    # 앵커는 풀에 있지만 겹치는 후보가 없음 → 소음 0
    entries = [_entry("terraform", "iac"), _entry("jest", "testing")]

    result = plan_try_this(["terraform"], entries, active_ids=set())

    assert result == []


def test_contract4_delegates_active_exclusion() -> None:
    entries = [_entry("terraform", "iac"), _entry("pulumi", "iac"), _entry("cdk", "iac")]

    # pulumi 이미 켬 → 비슷한 목록에서 빠짐(find_similar에 위임)
    result = plan_try_this(["terraform"], entries, active_ids={"pulumi"})

    assert {c.entry.id for c in result[0].similar} == {"cdk"}


def test_contract5_multiple_anchors_each_grouped() -> None:
    entries = [
        _entry("terraform", "iac"), _entry("pulumi", "iac"),
        _entry("jest", "testing"), _entry("vitest", "testing"),
    ]

    result = plan_try_this(["terraform", "jest"], entries, active_ids=set())

    anchors = {t.anchor_id for t in result}
    assert anchors == {"terraform", "jest"}


def test_contract6_is_pure() -> None:
    entries = [_entry("a", "x"), _entry("b", "x")]

    assert plan_try_this(["a"], entries, active_ids=set()) == plan_try_this(
        ["a"], entries, active_ids=set()
    )
