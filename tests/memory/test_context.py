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


def _boundary(name: str, scope: MemoryScope = MemoryScope.PROJECT) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=f"{name} 허용",
        body="force push 금지",
        type=MemoryType.BOUNDARY,
        scope=scope,
        created=date(2026, 6, 29),
    )


def test_boundary_pinned_above_other_memories() -> None:
    # Arrange — 일반 메모리와 경계를 섞는다
    user = _entry("prefers-uv", MemoryScope.GLOBAL)

    # Act
    out = render_context([user, _boundary("auto-commit")])

    # Assert — 경계 섹션이 일반 메모리보다 위
    assert "자율성 경계" in out
    assert out.index("자율성 경계") < out.index("prefers-uv")


def test_boundary_injects_body_and_scope() -> None:
    # Act
    out = render_context([_boundary("auto-commit", MemoryScope.PROJECT)])

    # Assert — 본문과 스코프가 함께 주입됨
    assert "force push 금지" in out
    assert "[project]" in out


def test_boundary_includes_safety_guidance() -> None:
    # Act
    out = render_context([_boundary("x", MemoryScope.GLOBAL)])

    # Assert — deny 넓게 / allow 좁게 해석 지침
    assert "금지" in out
    assert "허용" in out
