"""세션 컨텍스트 렌더링 — SessionStart hook이 에이전트에게 주입할 인덱스.

본문 전체가 아니라 인덱스(이름·성격·한 줄 요약)만 주입한다.
에이전트는 필요할 때 `pouch memory recall <키워드>`로 본문을 끌어온다.
"""

from __future__ import annotations

from collections.abc import Iterable

from pouch.memory.model import MemoryEntry, MemoryScope


def render_context(entries: Iterable[MemoryEntry]) -> str:
    """주입용 마크다운을 만든다. 기억이 없으면 빈 문자열(주입 생략)."""
    ordered = list(entries)
    if not ordered:
        return ""

    lines = [
        "# 🦦 pouch memory — 사용자에 대해 기억하는 것",
        "",
        "아래는 pouch가 기억해 둔 사용자·프로젝트 맥락이다. 이를 참고해 응답하라.",
        "더 자세한 내용이 필요하면 `pouch memory recall <키워드>`로 본문을 가져올 수 있다.",
        "",
    ]
    for scope in (MemoryScope.GLOBAL, MemoryScope.PROJECT):
        scoped = sorted(
            (entry for entry in ordered if entry.scope is scope),
            key=lambda entry: entry.name,
        )
        if not scoped:
            continue
        lines.append(f"## {scope.value}")
        lines.extend(
            f"- **{entry.name}** ({entry.type.value}) — {entry.description}" for entry in scoped
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
