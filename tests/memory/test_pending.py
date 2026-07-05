"""들어오는 문 — 타입별 마찰 판정(순수).

project·reference는 저마찰(pending 스테이징 허용) — 틀려도 위생이 나중에
쓸어간다. feedback·boundary·user는 확인 필수 — 오독한 지적이 매 세션
standing rule로 굳는 위험이 boundary deny 오독과 동형이라 pending 우회를 막는다.
"""

from __future__ import annotations

from datetime import date

from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState, MemoryType
from pouch.memory.pending import is_low_friction, pending_entries


def test_project_and_reference_are_low_friction() -> None:
    assert is_low_friction(MemoryType.PROJECT) is True
    assert is_low_friction(MemoryType.REFERENCE) is True


def test_feedback_boundary_user_require_confirmation() -> None:
    assert is_low_friction(MemoryType.FEEDBACK) is False
    assert is_low_friction(MemoryType.BOUNDARY) is False
    assert is_low_friction(MemoryType.USER) is False


def test_pending_entries_filters_only_pending_state() -> None:
    def _entry(name: str, state: MemoryState) -> MemoryEntry:
        return MemoryEntry(
            name=name, description="d", body="b", type=MemoryType.PROJECT,
            scope=MemoryScope.GLOBAL, created=date(2026, 1, 1), state=state,
        )

    entries = [
        _entry("staged", MemoryState.PENDING),
        _entry("active", MemoryState.INDEXED),
        _entry("demoted", MemoryState.ARCHIVED),
    ]

    result = pending_entries(entries)

    assert [e.name for e in result] == ["staged"]
