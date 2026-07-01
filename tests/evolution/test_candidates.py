"""drop 후보 산출 계약 검증 — 활성 표면 ∩ 집계 ∩ 임계 → 2단계 후보.

정책: 제안만(자동 제거 안 함). 2단계 —
  never-used + 유예 지남 → 강한 후보 (추천이 헛맞았다)
  썼지만 stale        → 약한 후보 (졸업했나?)
immunity(③ 강화 v0)는 별도 메커니즘이 아니라 stale 임계에서 자동으로 나온다:
최근 쓴 도구는 last_used가 신선해 stale이 안 된다.

  ① never-used + 유예 지남 → 후보 (reason=never-used)
  ② never-used + 유예 이내 → 후보 아님 (갓 설치 보호)
  ③ 최근 사용 → 후보 아님 (immunity)
  ④ 썼지만 stale → 후보 (reason=stale)
  ⑤ 집계엔 있지만 비활성 → 무시 (이미 떨어진 걸 재추천 안 함)
  ⑥ 정렬: 강한 후보(never-used) 먼저, 약한 후보(stale) 뒤
"""

from __future__ import annotations

from pouch.evolution.aggregate import UsageStat
from pouch.evolution.candidates import EvolveConfig, drop_candidates

_CFG = EvolveConfig(grace_days=14, stale_days=30)
_NOW = "2026-07-01T00:00:00"


def test_contract1_never_used_past_grace_is_candidate() -> None:
    active = {"aws-swift": "2026-06-01T00:00:00"}  # 30일 전 설치, 한 번도 안 씀

    cands = drop_candidates(active, {}, now=_NOW, config=_CFG)

    assert len(cands) == 1
    assert cands[0].entry_id == "aws-swift"
    assert cands[0].reason == "never-used"


def test_contract2_never_used_within_grace_protected() -> None:
    active = {"aws-swift": "2026-06-25T00:00:00"}  # 6일 전 설치 — 유예 이내

    assert drop_candidates(active, {}, now=_NOW, config=_CFG) == []


def test_contract3_recently_used_is_immune() -> None:
    active = {"aws-iam": "2026-01-01T00:00:00"}
    stats = {"aws-iam": UsageStat(count=5, last_used="2026-06-28T00:00:00")}  # 3일 전

    assert drop_candidates(active, stats, now=_NOW, config=_CFG) == []


def test_contract4_used_but_stale_is_candidate() -> None:
    active = {"aws-iam": "2026-01-01T00:00:00"}
    stats = {"aws-iam": UsageStat(count=2, last_used="2026-05-01T00:00:00")}  # 61일 전

    cands = drop_candidates(active, stats, now=_NOW, config=_CFG)

    assert len(cands) == 1
    assert cands[0].entry_id == "aws-iam"
    assert cands[0].reason == "stale"


def test_contract5_used_but_inactive_is_ignored() -> None:
    # 집계엔 있지만 활성 표면엔 없음 — 이미 떨어진 것. 재추천 금지.
    stats = {"gone": UsageStat(count=1, last_used="2026-01-01T00:00:00")}

    assert drop_candidates({}, stats, now=_NOW, config=_CFG) == []


def test_contract6_strong_candidates_sorted_first() -> None:
    active = {
        "stale-tool": "2026-01-01T00:00:00",
        "never-tool": "2026-01-01T00:00:00",
    }
    stats = {"stale-tool": UsageStat(count=1, last_used="2026-05-01T00:00:00")}

    cands = drop_candidates(active, stats, now=_NOW, config=_CFG)

    assert [c.reason for c in cands] == ["never-used", "stale"]


def test_default_config_has_sane_values() -> None:
    cfg = EvolveConfig()
    assert cfg.grace_days > 0
    assert cfg.stale_days > cfg.grace_days
