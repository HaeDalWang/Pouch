"""비슷한 것 찾기 계약 검증 — 앵커(반복 도구)의 토큰과 겹치는 풀 후보를 순위.

정책([[pouch-try-this-recommend-policy]] 조각 2 + 되살리기): "비슷하다"를 지어내지
않는다 — 토큰 겹침으로 판정(토큰은 도구가 달고 온 설명·태그·id). 왜 비슷한지
(shared_tokens)도 함께 낸다(실재 근거만). 설명 매칭은 시끄러워 최소 겹침 2로 방어.

  ① 앵커 토큰과 겹치는 후보를 겹침 수 내림차순으로
  ② 앵커 자신 제외
  ③ 이미 켠 것(active) 제외
  ④ 앵커가 풀에 없거나 토큰 없음 → [] (날것 예외)
  ⑤ 최소 겹침(2) 미만 → 노이즈로 버림
  ⑥ shared_tokens가 왜 비슷한지 실재 근거를 담는다
  ⑦ limit로 상한 / 순수 함수
"""

from __future__ import annotations

from pouch.evolution.pool import PoolEntry
from pouch.evolution.similar import SimilarCandidate, find_similar


def _p(id: str, *tokens: str) -> PoolEntry:
    return PoolEntry(id=id, description=f"{id} 설명", tokens=frozenset(tokens))


def test_contract1_ranks_by_overlap_count() -> None:
    pool = [
        _p("terraform", "iac", "cloud", "infra"),  # anchor
        _p("pulumi", "iac", "cloud", "infra"),  # 3겹
        _p("ansible", "infra", "config"),  # 1겹 → 최소겹침 미달로 컷
        _p("cdk", "iac", "cloud"),  # 2겹
    ]

    result = find_similar("terraform", pool, active_ids=set())

    ids = [c.entry.id for c in result]
    assert ids == ["pulumi", "cdk"]  # ansible은 1겹이라 컷


def test_contract2_excludes_anchor_itself() -> None:
    pool = [_p("terraform", "iac", "cloud"), _p("pulumi", "iac", "cloud")]

    result = find_similar("terraform", pool, active_ids=set())

    assert "terraform" not in [c.entry.id for c in result]


def test_contract3_excludes_active() -> None:
    pool = [
        _p("terraform", "iac", "cloud"),
        _p("pulumi", "iac", "cloud"),
        _p("cdk", "iac", "cloud"),
    ]

    # pulumi는 이미 표면에 켜져 있음 → 또 권하지 않음
    result = find_similar("terraform", pool, active_ids={"pulumi"})

    assert [c.entry.id for c in result] == ["cdk"]


def test_contract4_anchor_not_in_pool_is_empty() -> None:
    pool = [_p("pulumi", "iac", "cloud"), _p("cdk", "iac", "cloud")]

    assert find_similar("some-raw-command", pool, active_ids=set()) == []


def test_contract4b_anchor_without_tokens_is_empty() -> None:
    pool = [_p("bare"), _p("pulumi", "iac", "cloud")]

    assert find_similar("bare", pool, active_ids=set()) == []


def test_contract5_below_min_overlap_is_noise() -> None:
    # 단어 하나 스침(1겹)은 노이즈 — 최소 2겹 요구
    pool = [_p("terraform", "iac", "cloud"), _p("jest", "cloud", "testing")]

    assert find_similar("terraform", pool, active_ids=set()) == []


def test_contract6_shared_tokens_are_the_real_reason() -> None:
    pool = [_p("terraform", "iac", "cloud"), _p("cdk", "iac", "cloud", "aws")]

    result = find_similar("terraform", pool, active_ids=set())

    assert isinstance(result[0], SimilarCandidate)
    # 겹친 토큰만 근거로(앵커에 없는 aws는 근거 아님)
    assert result[0].shared_tokens == frozenset({"iac", "cloud"})


def test_contract7_limit_caps_results() -> None:
    pool = [_p("anchor", "t", "u")] + [_p(f"c{i}", "t", "u") for i in range(10)]

    result = find_similar("anchor", pool, active_ids=set(), limit=3)

    assert len(result) == 3


def test_contract8_is_pure() -> None:
    pool = [_p("a", "x", "y"), _p("b", "x", "y")]

    assert find_similar("a", pool, active_ids=set()) == find_similar(
        "a", pool, active_ids=set()
    )


def test_ties_broken_by_id() -> None:
    # 겹침 수 같으면 id 순(결정적)
    pool = [_p("anchor", "t", "u"), _p("zebra", "t", "u"), _p("apple", "t", "u")]

    result = find_similar("anchor", pool, active_ids=set())

    assert [c.entry.id for c in result] == ["apple", "zebra"]
