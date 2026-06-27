"""MEMORY.md 인덱스 렌더링/기록 검증."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pouch.memory.index import INDEX_FILENAME, render_index, write_index
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


def _entry(name: str) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=f"{name} 설명",
        body="본문",
        type=MemoryType.PROJECT,
        scope=MemoryScope.GLOBAL,
        created=date(2026, 6, 27),
    )


def test_render_lists_each_entry() -> None:
    # Act
    out = render_index([_entry("beta"), _entry("alpha")])

    # Assert — 사전순 정렬 + 둘 다 포함
    assert out.index("alpha") < out.index("beta")
    assert "(project)" in out


def test_render_empty_marks_empty() -> None:
    assert "비어있습니다" in render_index([])


def test_write_index_creates_file(tmp_path: Path) -> None:
    # Act
    path = write_index(tmp_path, [_entry("x")])

    # Assert
    assert path.name == INDEX_FILENAME
    assert "x" in path.read_text(encoding="utf-8")
