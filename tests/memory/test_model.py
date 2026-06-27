"""메모리 도메인 모델 직렬화/역직렬화 검증."""

from __future__ import annotations

from datetime import date

from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


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
