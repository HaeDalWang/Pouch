"""나가는 문 — 위생. 인덱스에서 강등할 후보를 제안한다(아무것도 강등 안 함).

핵심 비대칭(도구와 다름): 기억은 나이가 아니라 진실로 닳는다. `role:DevOps`는
안 봐도 안 낡고 `sprint 마감 다음 주`는 한 달 뒤 독이다. 그래서 붕괴 신호는
타입별로 갈린다 — 나이는 project에만 통하는 축이다:

  project    → 만료(created 기준 나이 > 임계). weight 면역 적용(내가 핀 건 안 나감).
  reference  → 생존성(가리키는 자원이 resolve 되나). weight 면역 없음 — 404는 못 살림.
  boundary   → 제외. 안 걸린 deny는 제 일을 하는 중(미사용 ≠ 불필요).
  feedback·user → v0에서 나갈 문 없음. 붕괴 신호가 모순뿐인데 그건 defer.
                  ⚠️ 인지된 갭 — 명시적 삭제로만 제거. 모순 감지가 나중에 메운다.

생존성 판정은 IO(파일 stat·HTTP)라 예측자(is_alive)로 주입받아 함수는 순수하게
둔다 — now를 주입하는 것과 같은 경계 원칙.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState, MemoryType

_PROJECT_TTL_DAYS = 45  # project 만료 임계(기본값; 매직넘버 회피)
_IMMUNE_WEIGHT = 3  # 이 이상이면 나이 기반 강등 제안에서 면역

REASON_EXPIRED = "expired"
REASON_DEAD_REFERENCE = "dead-reference"


@dataclass(frozen=True)
class HygieneCandidate:
    """인덱스에서 강등(→archived)을 제안할 후보. 강등은 사람 동의 후에만."""

    name: str
    scope: MemoryScope
    type: MemoryType
    reason: str  # REASON_EXPIRED | REASON_DEAD_REFERENCE
    detail: str


def hygiene_candidates(
    entries: list[MemoryEntry],
    *,
    now: date,
    is_alive: Callable[[MemoryEntry], bool],
    project_ttl_days: int = _PROJECT_TTL_DAYS,
    immune_weight: int = _IMMUNE_WEIGHT,
) -> list[HygieneCandidate]:
    """강등 후보를 뽑는다(제안만). INDEXED 계층만 대상."""
    found: list[HygieneCandidate] = []
    for entry in entries:
        if entry.state is not MemoryState.INDEXED:
            continue
        candidate = _judge(
            entry, now=now, is_alive=is_alive,
            project_ttl_days=project_ttl_days, immune_weight=immune_weight,
        )
        if candidate is not None:
            found.append(candidate)
    return sorted(found, key=lambda c: (c.reason, c.name))


def _judge(
    entry: MemoryEntry,
    *,
    now: date,
    is_alive: Callable[[MemoryEntry], bool],
    project_ttl_days: int,
    immune_weight: int,
) -> HygieneCandidate | None:
    """한 메모리의 타입별 붕괴 신호를 판정한다. 후보 아니면 None."""
    if entry.type is MemoryType.REFERENCE:
        # 생존성은 weight로 면역되지 않는다 — 죽은 자원은 죽었다.
        if not is_alive(entry):
            return _candidate(entry, REASON_DEAD_REFERENCE, "가리키는 자원이 사라졌습니다")
        return None

    if entry.type is MemoryType.PROJECT:
        if entry.weight >= immune_weight:
            return None  # 내가 핀 건 나이로 안 나간다
        age_days = (now - entry.created).days
        if age_days > project_ttl_days:
            return _candidate(entry, REASON_EXPIRED, f"{age_days}일 지남(임계 {project_ttl_days}일)")
        return None

    # boundary·feedback·user → v0에서 나갈 문 없음(제외/모순-defer).
    return None


def _candidate(entry: MemoryEntry, reason: str, detail: str) -> HygieneCandidate:
    return HygieneCandidate(
        name=entry.name, scope=entry.scope, type=entry.type, reason=reason, detail=detail
    )
