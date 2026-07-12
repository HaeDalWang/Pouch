"""추천 풀 계약 검증 — 카탈로그를 {id·설명·태그} 통합 뷰로 훑는다.

정책([[pouch-try-this-recommend-policy]] 조각 1): 풀 v0 = 카탈로그. 엔트리가 이미
{id·설명·태그}를 실어 온다(SKILL.md 파생, 우리가 안 지어냄). 읽기만·값쌈.

진짜 변환: 태그는 두 곳에 산다 — ToolEntry.tags(담을 때)와 Overlay.tags(vendored
개인화). 풀은 둘을 합친 통합 태그를 낸다(매칭이 한쪽만 보면 놓친다). 둘 다 진짜라
합쳐도 지어내기 없음.

  ① build_pool: 엔트리마다 PoolEntry(id·description·tags)
  ② 태그 병합: ToolEntry.tags ∪ Overlay.tags (중복 제거)
  ③ 태그 없는 엔트리(owned/linked, overlay=None) → 빈 태그 (크래시 없음)
  ④ 빈 카탈로그 → 빈 풀
  ⑤ 순수 함수 — 같은 입력 같은 출력, IO 없음
"""

from __future__ import annotations

from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.evolution.pool import PoolEntry, build_pool


def _vendored(id: str, *, tags=(), overlay_tags=()) -> ToolEntry:
    return ToolEntry.vendored(
        id=id, kind=ToolKind.SKILL, source="s", title=id, description=f"{id} 설명",
        upstream="/up", synced_at="2026-01-01", tags=tuple(tags),
        overlay=Overlay(tags=tuple(overlay_tags)) if overlay_tags else None,
    )


def test_contract1_maps_id_and_description() -> None:
    pool = build_pool([_vendored("terraform")])

    assert len(pool) == 1
    assert isinstance(pool[0], PoolEntry)
    assert pool[0].id == "terraform"
    assert pool[0].description == "terraform 설명"


def test_contract2_merges_both_tag_sources() -> None:
    # ToolEntry.tags와 Overlay.tags가 합쳐진다(중복 제거)
    entry = _vendored("tf", tags=("infra", "iac"), overlay_tags=("iac", "cloud"))

    pool = build_pool([entry])

    assert pool[0].tags == frozenset({"infra", "iac", "cloud"})


def test_contract3_no_tags_is_empty_not_crash() -> None:
    # owned/linked는 overlay=None — 크래시 없이 빈 태그
    owned = ToolEntry.owned(
        id="mytool", kind=ToolKind.COMMAND, source="s", title="t",
        description="d", body="b",
    )

    pool = build_pool([owned])

    assert pool[0].tags == frozenset()


def test_contract4_empty_catalog_is_empty_pool() -> None:
    assert build_pool([]) == []


def test_contract5_build_is_pure() -> None:
    entries = [_vendored("a", tags=("x",))]

    assert build_pool(entries) == build_pool(entries)
