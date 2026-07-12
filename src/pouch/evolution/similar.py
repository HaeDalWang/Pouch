"""비슷한 것 찾기 — 앵커(반복 도구)의 태그와 겹치는 풀 후보를 순위. 순수 함수.

정책([[pouch-try-this-recommend-policy]] 조각 2): 특정 패턴이 반복되면 비슷한 경우를
최대한 찾아 리스트로 준다(정답 아님, 후보). "비슷하다"를 우리가 지어내지 않는다 —
태그 겹침으로 판정(태그는 도구가 달고 온 사실). 왜 비슷한지(shared_tags)도 함께 내
실재하는 근거만 보여준다(지어내기 금지).

날것 예외: 앵커가 풀에 없거나(카탈로그 밖 도구) 태그가 없으면 비슷함을 판정할
근거가 없어 빈 리스트를 낸다 — 그 경우 호출부는 앵커 자체만 제안한다(v0 충분).
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.evolution.pool import PoolEntry

_DEFAULT_LIMIT = 5


@dataclass(frozen=True)
class SimilarCandidate:
    """비슷한 후보 하나 + 왜 비슷한지(겹친 태그, 실재 근거)."""

    entry: PoolEntry
    shared_tags: frozenset[str]

    @property
    def overlap(self) -> int:
        return len(self.shared_tags)


def find_similar(
    anchor_id: str,
    pool: list[PoolEntry],
    *,
    active_ids: set[str],
    limit: int = _DEFAULT_LIMIT,
) -> list[SimilarCandidate]:
    """앵커의 태그와 겹치는 후보를 겹침 수(내림차순)·id로 정렬해 돌려준다.

    앵커 자신·이미 켠 것(active)은 뺀다. 앵커가 풀에 없거나 태그가 없으면 []
    (날것 예외). 겹치는 게 하나도 없어도 [].
    """
    anchor_tags = _tags_of(anchor_id, pool)
    if not anchor_tags:  # 풀에 없거나 태그 없음 → 근거 없음
        return []

    candidates: list[SimilarCandidate] = []
    for entry in pool:
        if entry.id == anchor_id or entry.id in active_ids:
            continue
        shared = anchor_tags & entry.tags
        if shared:
            candidates.append(SimilarCandidate(entry=entry, shared_tags=shared))

    # 겹침 많은 순, 같으면 id 순(결정적).
    candidates.sort(key=lambda c: (-c.overlap, c.entry.id))
    return candidates[:limit]


def _tags_of(entry_id: str, pool: list[PoolEntry]) -> frozenset[str]:
    """풀에서 이 id의 태그를 찾는다. 없으면 빈 집합."""
    for entry in pool:
        if entry.id == entry_id:
            return entry.tags
    return frozenset()
