"""세션 컨텍스트 렌더링 검증."""

from __future__ import annotations

from datetime import date

from pouch.memory.context import render_context
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


def _entry(name: str, scope: MemoryScope = MemoryScope.GLOBAL) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=f"{name} 설명",
        body="본문",
        type=MemoryType.USER,
        scope=scope,
        created=date(2026, 6, 27),
    )


def test_empty_returns_blank() -> None:
    assert render_context([]) == ""


def test_includes_description_and_recall_hint() -> None:
    # Act
    out = render_context([_entry("prefers-uv")])

    # Assert
    assert "prefers-uv 설명" in out
    assert "recall" in out


def test_groups_by_scope() -> None:
    # Act
    out = render_context([_entry("g", MemoryScope.GLOBAL), _entry("p", MemoryScope.PROJECT)])

    # Assert
    assert "## global" in out
    assert "## project" in out
