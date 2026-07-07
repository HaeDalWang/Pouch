"""메모리 도메인 모델 직렬화/역직렬화 검증."""

from __future__ import annotations

from datetime import date

from pouch.memory.model import (
    Direction,
    MemoryEntry,
    MemoryScope,
    MemoryState,
    MemoryType,
)


def test_roundtrip_preserves_all_fields() -> None:
    # Arrange
    entry = MemoryEntry(
        name="prefers-uv",
        description="파이썬은 uv로 관리",
        body="사용자는 pip 대신 uv를 쓴다.\n여러 줄도 보존되어야 한다.",
        type=MemoryType.USER,
        scope=MemoryScope.GLOBAL,
        weight=3,
        created=date(2026, 6, 27),
    )

    # Act
    restored = MemoryEntry.from_markdown(entry.name, entry.to_markdown())

    # Assert
    assert restored == entry


def test_to_markdown_emits_frontmatter_and_body() -> None:
    # Arrange
    entry = MemoryEntry(
        name="note",
        description="짧은 메모",
        body="본문 한 줄",
        type=MemoryType.REFERENCE,
        scope=MemoryScope.PROJECT,
    )

    # Act
    text = entry.to_markdown()

    # Assert
    assert text.startswith("---")
    assert "type: reference" in text
    assert "scope: project" in text
    assert "본문 한 줄" in text


def test_weight_defaults_to_zero() -> None:
    # Arrange / Act
    entry = MemoryEntry(
        name="n",
        description="d",
        body="b",
        type=MemoryType.PROJECT,
        scope=MemoryScope.GLOBAL,
    )

    # Assert
    assert entry.weight == 0


def test_state_and_last_recalled_roundtrip() -> None:
    # Arrange — 기본값이 아닌 값이라야 직렬화가 검증된다
    entry = MemoryEntry(
        name="dashboard",
        description="관측 대시보드 링크",
        body="https://example.test/grafana",
        type=MemoryType.REFERENCE,
        scope=MemoryScope.GLOBAL,
        state=MemoryState.ARCHIVED,
        last_recalled=date(2026, 7, 5),
    )

    # Act
    restored = MemoryEntry.from_markdown(entry.name, entry.to_markdown())

    # Assert
    assert restored == entry
    assert restored.state is MemoryState.ARCHIVED
    assert restored.last_recalled == date(2026, 7, 5)


def test_state_defaults_to_indexed_and_last_recalled_none() -> None:
    # Arrange — state·last_recalled 필드가 없는 옛 형식(하위호환)
    old_format = (
        "---\n"
        "name: legacy\n"
        "description: 옛 메모리\n"
        "type: user\n"
        "scope: global\n"
        "weight: 0\n"
        "created: 2026-06-01\n"
        "---\n\n본문\n"
    )

    # Act
    entry = MemoryEntry.from_markdown("legacy", old_format)

    # Assert — 기존 메모리는 전부 indexed로, last_recalled는 비어서 로드된다
    assert entry.state is MemoryState.INDEXED
    assert entry.last_recalled is None


def test_indexed_state_omitted_from_markdown() -> None:
    # 기본(indexed)·last_recalled 없음이면 프론트매터에 잡음을 안 남긴다
    entry = MemoryEntry(
        name="n", description="d", body="b",
        type=MemoryType.PROJECT, scope=MemoryScope.GLOBAL,
    )

    text = entry.to_markdown()

    assert "state:" not in text
    assert "last_recalled:" not in text


def test_boundary_type_roundtrips() -> None:
    # Arrange
    entry = MemoryEntry(
        name="auto-commit",
        description="커밋 자율 허용",
        body="테스트 통과 시 커밋·푸시 자율. force push 금지.",
        type=MemoryType.BOUNDARY,
        scope=MemoryScope.PROJECT,
        created=date(2026, 6, 29),
    )

    # Act
    restored = MemoryEntry.from_markdown(entry.name, entry.to_markdown())

    # Assert
    assert restored == entry
    assert "type: boundary" in entry.to_markdown()


def test_boundary_direction_and_source_roundtrip() -> None:
    # Arrange — 도구가 딸고 온 '확인' 경계
    entry = MemoryEntry(
        name="prod-gate",
        description="prod 변경은 승인",
        body="prod 리소스 변경은 승인받아라.",
        type=MemoryType.BOUNDARY,
        scope=MemoryScope.GLOBAL,
        direction=Direction.ASK,
        source="vendored:aws-cdk",
        created=date(2026, 7, 7),
    )

    # Act
    restored = MemoryEntry.from_markdown(entry.name, entry.to_markdown())

    # Assert
    assert restored == entry
    assert restored.direction is Direction.ASK
    assert restored.source == "vendored:aws-cdk"


def test_boundary_direction_source_default_and_omitted() -> None:
    # 방향 불명(None) + 사람 출처(기본)는 프론트매터에 잡음을 안 남긴다
    entry = MemoryEntry(
        name="b", description="d", body="본문",
        type=MemoryType.BOUNDARY, scope=MemoryScope.PROJECT,
    )

    text = entry.to_markdown()

    assert "direction:" not in text
    assert "source:" not in text
    assert entry.direction is None
    assert entry.source == "user"


def test_legacy_boundary_loads_with_none_direction_user_source() -> None:
    # direction·source 필드가 없는 옛 boundary(하위호환)
    old = (
        "---\n"
        "name: auto-commit\n"
        "description: 커밋 자율 허용\n"
        "type: boundary\n"
        "scope: project\n"
        "weight: 0\n"
        "created: 2026-06-29\n"
        "---\n\n테스트 통과 시 커밋 자율.\n"
    )

    entry = MemoryEntry.from_markdown("auto-commit", old)

    # 방향 불명은 gate에서 '잔존'으로 안전하게 취급되고, 출처는 사람으로 본다
    assert entry.direction is None
    assert entry.source == "user"
