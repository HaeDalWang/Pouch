"""세션 컨텍스트 렌더링 — SessionStart hook이 에이전트에게 주입할 인덱스.

일반 메모리는 인덱스(이름·성격·한 줄 요약)만 주입한다.
에이전트는 필요할 때 `pouch memory recall <키워드>`로 본문을 끌어온다.

단 `boundary`(자율성/신뢰 경계)는 예외다. 본문까지 최상단에 강조 주입하며,
"금지는 넓게, 허용은 좁게"라는 해석 지침을 함께 박아 deny 오독을 완화한다.
허용 누수(A 프로젝트 → B)는 scope 저장 구조가 막는다(프로젝트 경계는 그 repo에서만 읽힘).
"""

from __future__ import annotations

from collections.abc import Iterable

from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


def render_context(entries: Iterable[MemoryEntry]) -> str:
    """주입용 마크다운을 만든다. 기억이 없으면 빈 문자열(주입 생략)."""
    ordered = list(entries)
    if not ordered:
        return ""

    boundaries = sorted(
        (entry for entry in ordered if entry.type is MemoryType.BOUNDARY),
        key=lambda entry: entry.name,
    )
    others = [entry for entry in ordered if entry.type is not MemoryType.BOUNDARY]

    lines = [
        "# 🦦 pouch memory — 사용자에 대해 기억하는 것",
        "",
        "아래는 pouch가 기억해 둔 사용자·프로젝트 맥락이다. 이를 참고해 응답하라.",
        "더 자세한 내용이 필요하면 `pouch memory recall <키워드>`로 본문을 가져올 수 있다.",
        "",
    ]
    if boundaries:
        lines.extend(_render_boundaries(boundaries))
    lines.extend(_render_scoped(others))
    return "\n".join(lines).rstrip() + "\n"


def _render_boundaries(boundaries: list[MemoryEntry]) -> list[str]:
    """자율성 경계를 본문까지 포함해 최상단에 강조 렌더링한다."""
    lines = [
        "## ⚠️ 자율성 경계 — 반드시 따를 것",
        "",
        "금지(deny)는 항상 우선하며 넓게 해석하라. "
        "허용(allow)은 아래에 적힌 범위 안에서만 좁게 적용하라. "
        "프로젝트 범위 허용을 이 프로젝트 밖으로 확장하지 마라.",
        "",
    ]
    for entry in boundaries:
        lines.append(f"- **{entry.name}** [{entry.scope.value}] — {entry.description}")
        body = entry.body.strip()
        if body:
            lines.extend(f"  {body_line}" for body_line in body.splitlines())
    lines.append("")
    return lines


def _render_scoped(entries: list[MemoryEntry]) -> list[str]:
    """일반 메모리를 스코프별로 인덱스만 렌더링한다."""
    lines: list[str] = []
    for scope in (MemoryScope.GLOBAL, MemoryScope.PROJECT):
        scoped = sorted(
            (entry for entry in entries if entry.scope is scope),
            key=lambda entry: entry.name,
        )
        if not scoped:
            continue
        lines.append(f"## {scope.value}")
        lines.extend(
            f"- **{entry.name}** ({entry.type.value}) — {entry.description}" for entry in scoped
        )
        lines.append("")
    return lines
