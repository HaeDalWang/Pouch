"""키워드 회상 로직 검증."""

from __future__ import annotations

from datetime import date

from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType
from pouch.memory.recall import recall, touch_recalled


def _entry(name: str, body: str, weight: int = 0) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description="설명",
        body=body,
        type=MemoryType.USER,
        scope=MemoryScope.GLOBAL,
        weight=weight,
        created=date(2026, 6, 27),
    )


def test_matches_in_body() -> None:
    # Arrange
    entries = [_entry("a", "파이썬은 uv로 관리"), _entry("b", "고랭 이야기")]

    # Act
    hits = recall(entries, "파이썬")

    # Assert
    assert [h.name for h in hits] == ["a"]


def test_blank_query_returns_empty() -> None:
    assert recall([_entry("a", "내용")], "   ") == []


def test_orders_by_occurrence_count() -> None:
    # Arrange
    many = _entry("many", "uv uv uv")
    few = _entry("few", "uv")

    # Act
    hits = recall([few, many], "uv")

    # Assert
    assert [h.name for h in hits] == ["many", "few"]


def test_weight_breaks_into_score() -> None:
    # Arrange — 같은 등장 횟수면 weight 높은 쪽이 앞
    heavy = _entry("heavy", "uv", weight=5)
    light = _entry("light", "uv", weight=0)

    # Act
    hits = recall([light, heavy], "uv")

    # Assert
    assert [h.name for h in hits] == ["heavy", "light"]


def test_respects_limit() -> None:
    entries = [_entry(f"n{i}", "uv") for i in range(5)]
    assert len(recall(entries, "uv", limit=2)) == 2


def test_touch_recalled_sets_last_recalled_to_now() -> None:
    # Arrange
    entry = _entry("a", "본문")

    # Act
    touched = touch_recalled([entry], now=date(2026, 7, 5))

    # Assert
    assert touched[0].last_recalled == date(2026, 7, 5)


def test_touch_recalled_does_not_mutate_original() -> None:
    # 불변 원칙 — 새 인스턴스를 반환하고 원본은 그대로
    entry = _entry("a", "본문")

    touch_recalled([entry], now=date(2026, 7, 5))

    assert entry.last_recalled is None


def test_touch_recalled_preserves_other_fields() -> None:
    entry = _entry("a", "본문", weight=2)

    touched = touch_recalled([entry], now=date(2026, 7, 5))[0]

    assert touched.name == entry.name
    assert touched.weight == entry.weight
    assert touched.body == entry.body
