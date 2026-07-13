"""추천 풀 계약 검증 — 카탈로그를 {id·설명·매칭토큰} 뷰로 훑는다.

정책([[pouch-try-this-recommend-policy]] 조각 1 + 되살리기): 풀 v0 = 카탈로그.
엔트리가 이미 {id·설명·태그}를 실어 온다(SKILL.md 파생) — 우리가 안 지어낸다.

매칭 신호 전환(2026-07-13): 실측 태그 0/201, 설명 194/201 살아있음 → 매칭을
태그에서 **설명 토큰 겹침**으로. 설명도 도구가 달고 온 사실(SKILL.md)이라 지어내기
아님. 노이즈 방어: 불용어(언어 기능어만, 도구 큐레이션 아님) + 짧은 토큰 제거.
태그·id도 있으면 토큰에 함께 접는다(있는 신호 다 씀, 미래 대비).

  ① build_pool: 엔트리마다 PoolEntry(id·description·tokens)
  ② tokens는 설명에서 뽑는다("web search research" → {web,search,research})
  ③ 불용어 제거(the·for·use·when 등 기능어 — 도구 판단 아님)
  ④ 태그·id도 토큰에 접힌다(있는 신호 다)
  ⑤ 짧은 토큰(1글자) 제거하되 'go' 같은 2글자 도메인어는 보존
  ⑥ 빈 카탈로그 → 빈 풀 / 순수 함수
"""

from __future__ import annotations

from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.evolution.pool import PoolEntry, build_pool


def _vendored(id: str, *, description: str, tags=(), overlay_tags=()) -> ToolEntry:
    return ToolEntry.vendored(
        id=id, kind=ToolKind.SKILL, source="s", title=id, description=description,
        upstream="/up", synced_at="2026-01-01", tags=tuple(tags),
        overlay=Overlay(tags=tuple(overlay_tags)) if overlay_tags else None,
    )


def test_contract1_maps_id_and_description() -> None:
    pool = build_pool([_vendored("exa", description="web search and research")])

    assert len(pool) == 1
    assert isinstance(pool[0], PoolEntry)
    assert pool[0].id == "exa"
    assert pool[0].description == "web search and research"


def test_contract2_tokens_from_description() -> None:
    pool = build_pool([_vendored("exa", description="web search research")])

    assert {"web", "search", "research"} <= pool[0].tokens


def test_contract3_stopwords_removed() -> None:
    # 기능어(use·this·for·when·and)는 노이즈라 뺀다 — 도구 판단이 아니라 언어 정리
    pool = build_pool([_vendored("x", description="use this skill for research when needed")])

    assert "research" in pool[0].tokens
    for stop in ("use", "this", "for", "when", "and"):
        assert stop not in pool[0].tokens


def test_contract4_folds_tags_and_id() -> None:
    entry = _vendored("aws-iam", description="access management", tags=("cloud",), overlay_tags=("infra",))

    tokens = build_pool([entry])[0].tokens

    # 설명 + 태그(양쪽) + id 토큰 모두 접힌다
    assert {"access", "management", "cloud", "infra", "aws", "iam"} <= tokens


def test_contract5_short_tokens_dropped_but_keeps_go() -> None:
    # 1글자는 노이즈로 제거, 2글자 도메인어(go)는 보존
    pool = build_pool([_vendored("golang", description="go testing a b")])

    assert "go" in pool[0].tokens
    assert "a" not in pool[0].tokens
    assert "b" not in pool[0].tokens


def test_contract6_empty_and_pure() -> None:
    assert build_pool([]) == []
    e = [_vendored("a", description="foo bar")]
    assert build_pool(e) == build_pool(e)
