"""승격 통로 — 엔트리의 권장 boundary를 진짜 boundary 메모리로 태어나게 한다.

P1의 심장. "도구가 딸고 온 boundary"의 정체는 이 함수가 만든다: 카탈로그
엔트리(RecommendedBoundary 씨앗)를 설치할 때 boundary 메모리로 승격하며
source=vendored:<엔트리id>를 도장 찍는다. 그 출처가 drop gate의 열쇠다.

순수 함수(IO 없음) — 설치 커맨드가 이 결과를 memory store에 저장한다.
카탈로그→메모리 정방향 의존이라 순환 없다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pouch.catalog.model import ToolEntry
from pouch.memory.model import (
    VENDORED_SOURCE_PREFIX,
    Direction,
    MemoryEntry,
    MemoryType,
)


def recommended_boundary_memories(entry: ToolEntry, *, now: date) -> list[MemoryEntry]:
    """엔트리가 딸고 온 권장 boundary들을 boundary 메모리로 변환한다.

    각 메모리는 source=vendored:<엔트리id>를 달아 출처를 새긴다 — 사람이 직접 건
    boundary(source=user)와 구분되어, 도구 drop 시 방향(direction)에 따라 처리된다.
    """
    source = f"{VENDORED_SOURCE_PREFIX}{entry.id}"
    return [
        MemoryEntry(
            name=rec.name,
            description=rec.description,
            body=rec.body,
            type=MemoryType.BOUNDARY,
            scope=rec.scope,
            direction=rec.direction,
            source=source,
            created=now,
        )
        for rec in entry.recommended_boundaries
    ]


@dataclass(frozen=True)
class BoundaryDropPlan:
    """도구 drop 시 그 도구 출신 boundary를 어떻게 할지의 계획(순수 산출).

    to_demote : 함께 강등할 것(allow — 허용은 도구 없이 떠돌면 위험).
    to_keep   : 잔존시킬 것(ask/deny/방향불명 — 사라지는 게 위험, 경고 동반).
    사람이 건 것(source=user)과 다른 도구 출신은 아예 대상이 아니라 둘 다에 없다.
    """

    to_demote: tuple[MemoryEntry, ...] = ()
    to_keep: tuple[MemoryEntry, ...] = ()


def plan_boundary_drop(
    memories: list[MemoryEntry], dropped_entry_id: str
) -> BoundaryDropPlan:
    """내려가는 도구가 딸고 왔던 boundary를 방향으로 가른다(IO 없음).

    이 도구 출신(source=vendored:<id>)만 대상. allow는 함께 강등, 그 외(ask·deny·
    방향불명)는 잔존. 사람이 건 것·다른 도구 출신은 손대지 않는다(둘 다에서 제외).
    """
    dropped_source = f"{VENDORED_SOURCE_PREFIX}{dropped_entry_id}"
    to_demote: list[MemoryEntry] = []
    to_keep: list[MemoryEntry] = []
    for mem in memories:
        if mem.type is not MemoryType.BOUNDARY or mem.source != dropped_source:
            continue
        if mem.direction is Direction.ALLOW:
            to_demote.append(mem)
        else:
            to_keep.append(mem)
    return BoundaryDropPlan(to_demote=tuple(to_demote), to_keep=tuple(to_keep))
