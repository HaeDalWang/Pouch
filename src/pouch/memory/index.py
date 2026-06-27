"""MEMORY.md 인덱스 — 스코프 디렉토리마다 한 줄 한 메모리로 요약.

SessionStart hook이 본문 전체 대신 이 인덱스를 컨텍스트에 주입할 수 있어
토큰을 아끼면서 "무엇이 기억돼 있는지"를 에이전트에게 알린다.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pouch.memory.model import MemoryEntry

INDEX_FILENAME = "MEMORY.md"


def render_index(entries: Iterable[MemoryEntry]) -> str:
    """메모리 목록을 인덱스 마크다운 문자열로 렌더링한다."""
    ordered = sorted(entries, key=lambda entry: entry.name)
    lines = ["# pouch memory", ""]
    if not ordered:
        lines.append("_아직 비어있습니다._")
    else:
        lines.extend(
            f"- **{entry.name}** ({entry.type.value}) — {entry.description}" for entry in ordered
        )
    return "\n".join(lines) + "\n"


def write_index(directory: Path, entries: Iterable[MemoryEntry]) -> Path:
    """디렉토리에 MEMORY.md를 기록하고 그 경로를 반환한다."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / INDEX_FILENAME
    path.write_text(render_index(entries), encoding="utf-8")
    return path
