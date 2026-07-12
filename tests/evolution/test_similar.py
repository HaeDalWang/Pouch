"""비슷한 것 찾기 계약 검증 — 앵커(반복 도구)의 태그와 겹치는 풀 후보를 순위.

정책([[pouch-try-this-recommend-policy]] 조각 2): "특정 패턴이 반복되면 비슷한 경우를
최대한 찾아 리스트로 주고, 이 중 해볼래". "비슷하다"를 우리가 지어내지 않는다 —
태그 겹침으로 판정(태그는 도구가 달고 온 사실). 왜 비슷한지(겹친 태그)도 함께 낸다
(실재하는 근거만 보여줌 = 지어내기 금지).

  ① 앵커 태그와 겹치는 후보를 겹침 수 내림차순으로
  ② 앵커 자신은 제외(자기를 비슷하다 하지 않음)
  ③ 이미 켠 것(active) 제외 — 이미 있는 걸 또 권하지 않음
  ④ 앵커가 풀에 없거나 태그 없음 → [] (날것 예외, 비슷한 것 못 줌)
  ⑤ 겹치는 게 하나도 없음 → []
  ⑥ shared_tags가 왜 비슷한지 실재 근거를 담는다
  ⑦ limit로 상한
  ⑧ 순수 함수
"""

from __future__ import annotations

from pouch.evolution.pool import PoolEntry
from pouch.evolution.similar import SimilarCandidate, find_similar


def _p(id: str, *tags: str) -> PoolEntry:
    return PoolEntry(id=id, description=f"{id} 설명", tags=frozenset(tags))


def test_contract1_ranks_by_overlap_count() -> None:
    pool = [
        _p("terraform", "iac", "cloud", "infra"),  # anchor
        _p("pulumi", "iac", "cloud", "infra"),  # 3겹
        _p("ansible", "infra"),  # 1겹
        _p("cdk", "iac", "cloud"),  # 2겹
    ]

    result = find_similar("terraform", pool, active_ids=set())

    ids = [c.entry.id for c in result]
    assert ids == ["pulumi", "cdk", "ansible"]  # 겹침 많은 순


def test_contract2_excludes_anchor_itself() -> None:
    pool = [_p("terraform", "iac"), _p("pulumi", "iac")]

    result = find_similar("terraform", pool, active_ids=set())

    assert "terraform" not in [c.entry.id for c in result]


def test_contract3_excludes_active() -> None:
    pool = [_p("terraform", "iac"), _p("pulumi", "iac"), _p("cdk", "iac")]

    # pulumi는 이미 표면에 켜져 있음 → 또 권하지 않음
    result = find_similar("terraform", pool, active_ids={"pulumi"})

    assert [c.entry.id for c in result] == ["cdk"]


def test_contract4_anchor_not_in_pool_is_empty() -> None:
    # adopt 후보처럼 카탈로그 밖 도구(풀에 없음) → 비슷한 것 못 줌(날것 예외)
    pool = [_p("pulumi", "iac"), _p("cdk", "iac")]

    assert find_similar("some-raw-command", pool, active_ids=set()) == []


def test_contract4b_anchor_without_tags_is_empty() -> None:
    # 앵커가 풀에 있어도 태그가 없으면 비슷함을 판정할 근거가 없음
    pool = [_p("bare"), _p("pulumi", "iac")]

    assert find_similar("bare", pool, active_ids=set()) == []


def test_contract5_no_overlap_is_empty() -> None:
    pool = [_p("terraform", "iac"), _p("jest", "testing"), _p("pytest", "testing")]

    assert find_similar("terraform", pool, active_ids=set()) == []


def test_contract6_shared_tags_are_the_real_reason() -> None:
    pool = [_p("terraform", "iac", "cloud"), _p("cdk", "iac", "cloud", "aws")]

    result = find_similar("terraform", pool, active_ids=set())

    assert isinstance(result[0], SimilarCandidate)
    # 겹친 태그만 근거로(앵커에 없는 aws는 근거 아님)
    assert result[0].shared_tags == frozenset({"iac", "cloud"})


def test_contract7_limit_caps_results() -> None:
    pool = [_p("anchor", "t")] + [_p(f"c{i}", "t") for i in range(10)]

    result = find_similar("anchor", pool, active_ids=set(), limit=3)

    assert len(result) == 3


def test_contract8_is_pure() -> None:
    pool = [_p("a", "x"), _p("b", "x")]

    assert find_similar("a", pool, active_ids=set()) == find_similar(
        "a", pool, active_ids=set()
    )


def test_ties_broken_by_id() -> None:
    # 겹침 수 같으면 id 순(결정적)
    pool = [_p("anchor", "t"), _p("zebra", "t"), _p("apple", "t")]

    result = find_similar("anchor", pool, active_ids=set())

    assert [c.entry.id for c in result] == ["apple", "zebra"]
