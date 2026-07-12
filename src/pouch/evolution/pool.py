"""추천 풀 — 카탈로그를 {id·설명·태그} 통합 뷰로 훑는다. 순수 함수.

정책([[pouch-try-this-recommend-policy]] 조각 1): 풀 v0 = 카탈로그. 엔트리가 이미
{id·설명·태그}를 실어 온다(SKILL.md 파생) — 우리가 지어내지 않는다. 읽기만·값쌈.
"이거 써봐"에서 "무엇을 추천"의 후보 원천이 이 풀이다.

진짜 변환: 태그는 두 곳에 산다 — ToolEntry.tags(담을 때 붙은 것)와 Overlay.tags
(vendored 개인화). 매칭이 한쪽만 보면 후보를 놓치므로 풀은 둘을 합쳐 통합 태그를
낸다. 둘 다 진짜(도구 파생·사용자 개인화)라 합쳐도 지어내기가 없다.

바깥 마켓 소스는 나중 — v0는 이미 깔린 것(카탈로그)만(배승도 범위 결정).
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.catalog.model import ToolEntry


@dataclass(frozen=True)
class PoolEntry:
    """추천 후보 하나 — 매칭에 필요한 최소 뷰(카탈로그에서 파생, 지어내기 없음)."""

    id: str
    description: str
    tags: frozenset[str]


def _merged_tags(entry: ToolEntry) -> frozenset[str]:
    """엔트리의 통합 태그 — ToolEntry.tags ∪ Overlay.tags(둘 다 진짜)."""
    tags = set(entry.tags)
    if entry.overlay is not None:
        tags |= set(entry.overlay.tags)
    return frozenset(tags)


def build_pool(entries: list[ToolEntry]) -> list[PoolEntry]:
    """카탈로그 엔트리를 추천 후보 뷰로 접는다(읽기만, 순서 보존)."""
    return [
        PoolEntry(id=entry.id, description=entry.description, tags=_merged_tags(entry))
        for entry in entries
    ]
