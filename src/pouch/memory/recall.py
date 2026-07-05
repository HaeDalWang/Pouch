"""메모리 회상 — Phase 1은 KISS 원칙으로 키워드 매칭부터.

시맨틱(임베딩) 검색은 진화 단계(Phase 4)에서 weight와 함께 도입한다.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date

from pouch.memory.model import MemoryEntry


def recall(entries: Iterable[MemoryEntry], query: str, limit: int = 5) -> list[MemoryEntry]:
    """`query`를 포함하는 메모리를 점수순으로 반환한다.

    점수 = (이름·설명·본문에서 등장 횟수) + weight. 동점이면 이름 사전순.
    """
    needle = query.strip().lower()
    if not needle:
        return []

    scored: list[tuple[int, MemoryEntry]] = []
    for entry in entries:
        haystack = f"{entry.name} {entry.description} {entry.body}".lower()
        occurrences = haystack.count(needle)
        if occurrences == 0:
            continue
        scored.append((occurrences + entry.weight, entry))

    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    return [entry for _, entry in scored[:limit]]


def touch_recalled(entries: list[MemoryEntry], *, now: date) -> list[MemoryEntry]:
    """recall된 항목들의 last_recalled를 now로 갱신한 새 목록을 반환한다(순수, 불변).

    구조 슬롯(last_recalled)의 v0 로직 — 실제 저장(store.save)은 호출부(CLI 경계)의 몫.
    """
    return [replace(entry, last_recalled=now) for entry in entries]
