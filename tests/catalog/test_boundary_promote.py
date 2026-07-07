"""승격 통로 검증 — 엔트리의 권장 boundary → boundary 메모리(출처 도장).

P1의 심장: "도구가 딸고 온 boundary"의 정체는 마법이 아니라, 엔트리에 붙은
권장 boundary가 설치 시 진짜 메모리로 태어나며 source=vendored:<id>를 다는 것.
그 출처 도장이 7단계 drop gate가 "무엇을 함께 내릴지" 가르는 열쇠다.
"""

from __future__ import annotations

from datetime import date

from pouch.catalog.boundary import recommended_boundary_memories
from pouch.catalog.model import RecommendedBoundary, ToolEntry, ToolKind
from pouch.memory.model import Direction, MemoryScope, MemoryType


def _entry_with(*recs: RecommendedBoundary) -> ToolEntry:
    return ToolEntry.vendored(
        id="aws-cdk",
        kind=ToolKind.SKILL,
        source="aws",
        title="AWS CDK",
        description="CDK 절차",
        upstream="/x/SKILL.md",
        synced_at="2026-07-07",
    ).with_recommended_boundaries(recs)


def test_no_recommendations_yields_nothing() -> None:
    entry = _entry_with()
    assert recommended_boundary_memories(entry, now=date(2026, 7, 7)) == []


def test_recommendation_becomes_boundary_memory_with_vendored_source() -> None:
    # Arrange — CDK가 "prod 변경은 승인" 확인 경계를 딸고 온다
    entry = _entry_with(
        RecommendedBoundary(
            name="cdk-prod-gate",
            description="prod 변경은 승인",
            body="prod 스택 배포는 승인받아라.",
            direction=Direction.ASK,
            scope=MemoryScope.GLOBAL,
        )
    )

    # Act
    mems = recommended_boundary_memories(entry, now=date(2026, 7, 7))

    # Assert — 진짜 boundary 메모리로, 출처 도장이 찍힌다
    assert len(mems) == 1
    mem = mems[0]
    assert mem.type is MemoryType.BOUNDARY
    assert mem.direction is Direction.ASK
    assert mem.source == "vendored:aws-cdk"  # 출처 = 이 도구
    assert mem.scope is MemoryScope.GLOBAL
    assert mem.created == date(2026, 7, 7)


def test_multiple_recommendations_each_stamped() -> None:
    entry = _entry_with(
        RecommendedBoundary(
            name="cdk-prod-gate", description="prod 승인", body="...",
            direction=Direction.ASK, scope=MemoryScope.GLOBAL,
        ),
        RecommendedBoundary(
            name="cdk-dev-auto", description="dev 자율", body="...",
            direction=Direction.ALLOW, scope=MemoryScope.PROJECT,
        ),
    )

    mems = recommended_boundary_memories(entry, now=date(2026, 7, 7))

    assert {m.name for m in mems} == {"cdk-prod-gate", "cdk-dev-auto"}
    assert all(m.source == "vendored:aws-cdk" for m in mems)


def test_recommended_boundaries_roundtrip_in_catalog() -> None:
    # 엔트리에 붙인 권장 boundary가 직렬화/역직렬화로 보존된다
    entry = _entry_with(
        RecommendedBoundary(
            name="cdk-prod-gate", description="prod 승인", body="prod 배포는 승인.",
            direction=Direction.ASK, scope=MemoryScope.GLOBAL,
        )
    )

    restored = ToolEntry.from_markdown(entry.to_markdown())

    assert restored.recommended_boundaries == entry.recommended_boundaries
    assert restored.recommended_boundaries[0].direction is Direction.ASK


def test_entry_without_recommendations_omits_field_from_markdown() -> None:
    entry = _entry_with()
    assert "recommended_boundaries" not in entry.to_markdown()
