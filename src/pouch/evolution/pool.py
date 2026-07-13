"""추천 풀 — 카탈로그를 {id·설명·매칭토큰} 뷰로 훑는다. 순수 함수.

정책([[pouch-try-this-recommend-policy]] 조각 1 + 되살리기): 풀 v0 = 카탈로그.
엔트리가 이미 {id·설명·태그}를 실어 온다(SKILL.md 파생) — 우리가 안 지어낸다.

매칭 신호 전환(2026-07-13): 실측 태그 0/201, 설명 194/201 살아있음 → 매칭을 태그에서
**설명 토큰 겹침**으로 옮긴다. 설명도 도구가 달고 온 사실(SKILL.md)이라 지어내기 아님 —
"토큰이 겹친다"는 기계적 판정이지 우리가 큐레이션하는 게 아니다. 있는 신호를 다 쓰려고
설명·태그(양쪽)·id를 한 토큰 집합으로 접는다.

노이즈 방어(설명 매칭은 태그보다 시끄럽다): 불용어(언어 기능어만 — 도구 큐레이션이
아니라 the·for·use 같은 노이즈 제거) + 1글자 토큰 제거. 2글자 도메인어(go)는 보존.
바깥 마켓 소스는 나중 — v0는 카탈로그만(배승도 범위 결정).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pouch.catalog.model import ToolEntry

# 토큰 경계: 영숫자 아닌 것 전부.
_TOKEN_RE = re.compile(r"[^a-z0-9]+")

# 언어 기능어 — 설명에 흔하나 의미 신호가 아니다(도구 판단 아님, 언어 노이즈).
# 도구 종류를 큐레이션하는 게 아니라 매칭을 흐리는 잡음만 뺀다.
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by",
    "is", "are", "be", "as", "at", "from", "this", "that", "it", "its", "your",
    "you", "use", "used", "using", "when", "where", "which", "who", "what", "how",
    "can", "will", "should", "must", "may", "into", "via", "per", "not", "no",
    "skill", "tool", "tools", "helps", "help", "etc",
})


@dataclass(frozen=True)
class PoolEntry:
    """추천 후보 하나 — 매칭에 필요한 최소 뷰(카탈로그에서 파생, 지어내기 없음)."""

    id: str
    description: str
    tokens: frozenset[str]


def _tokenize(text: str) -> set[str]:
    """텍스트를 소문자 토큰 집합으로. 불용어·1글자 제거(2글자 도메인어는 보존)."""
    raw = {tok for tok in _TOKEN_RE.split(text.lower()) if tok}
    return {tok for tok in raw if len(tok) >= 2 and tok not in _STOPWORDS}


def _tokens_of(entry: ToolEntry) -> frozenset[str]:
    """엔트리의 매칭 토큰 — 설명 + 태그(양쪽) + id를 다 접는다(있는 신호 다)."""
    text_parts = [entry.description, entry.id.replace("-", " ")]
    text_parts.extend(entry.tags)
    if entry.overlay is not None:
        text_parts.extend(entry.overlay.tags)
    tokens: set[str] = set()
    for part in text_parts:
        tokens |= _tokenize(part)
    return frozenset(tokens)


def build_pool(entries: list[ToolEntry]) -> list[PoolEntry]:
    """카탈로그 엔트리를 추천 후보 뷰로 접는다(읽기만, 순서 보존)."""
    return [
        PoolEntry(id=entry.id, description=entry.description, tokens=_tokens_of(entry))
        for entry in entries
    ]
