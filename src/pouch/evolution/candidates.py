"""drop 후보 산출 — 활성 표면 ∩ 집계 ∩ 임계 → 2단계 후보. 순수 함수.

정책: 제안만(자동 제거 안 함). "떨어진다 ≠ 삭제된다" — 여기선 후보만 고른다.
2단계:
  never-used + 유예 지남 → 강한 후보 (추천이 헛맞았다)
  썼지만 stale        → 약한 후보 (졸업했나?)

immunity(③ 강화 v0)는 별도 메커니즘이 아니라 stale 임계에서 자동으로 나온다:
최근 쓴 도구는 last_used가 신선해 stale 후보가 안 된다(수동적 강화).

now는 주입한다 — 순수 함수는 시계를 만들지 않는다(ISO 파싱만).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pouch.evolution.aggregate import UsageStat

_DEFAULT_GRACE_DAYS = 14
_DEFAULT_STALE_DAYS = 30

# 정렬: 강한 후보(never-used) 먼저, 약한 후보(stale) 뒤.
_REASON_ORDER = {"never-used": 0, "stale": 1}


@dataclass(frozen=True)
class EvolveConfig:
    """임계값 — 매직넘버 회피, 기본값 있는 config."""

    grace_days: int = _DEFAULT_GRACE_DAYS  # 갓 설치된 도구 보호 기간
    stale_days: int = _DEFAULT_STALE_DAYS  # 이만큼 안 쓰면 stale


@dataclass(frozen=True)
class DropCandidate:
    """drop 제안 후보. reason으로 강/약을 구분한다."""

    entry_id: str
    reason: str  # "never-used" | "stale"


def _days_between(earlier: str, later: str) -> float:
    """ISO8601 두 시각 사이 일수. earlier가 미래면 음수."""
    return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds() / 86400


def drop_candidates(
    active: dict[str, str],
    stats: dict[str, UsageStat],
    *,
    now: str,
    config: EvolveConfig,
) -> list[DropCandidate]:
    """활성 표면(entry_id→installed_at ISO)에서 drop 후보를 고른다.

    집계엔 있지만 비활성인 건 무시한다 — 이미 떨어진 걸 재추천하지 않는다.
    """
    candidates: list[DropCandidate] = []
    for entry_id, installed_at in active.items():
        stat = stats.get(entry_id)
        if stat is None:
            # 한 번도 안 씀 — 유예기간이 지났을 때만 후보(갓 설치 보호).
            if _days_between(installed_at, now) >= config.grace_days:
                candidates.append(DropCandidate(entry_id, "never-used"))
        else:
            # 썼지만 마지막 사용이 stale 임계를 넘었나(immunity의 반대).
            if _days_between(stat.last_used, now) >= config.stale_days:
                candidates.append(DropCandidate(entry_id, "stale"))
    return sorted(candidates, key=lambda c: (_REASON_ORDER[c.reason], c.entry_id))
