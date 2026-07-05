"""memory evolve orchestration — 들어오는 문·나가는 문을 계획한다(제안만)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pouch.memory.evolve import plan_memory_hygiene, plan_memory_pending
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState, MemoryType
from pouch.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(global_dir=tmp_path / "global", project_dir=tmp_path / "project")


def test_plan_memory_pending_returns_only_pending(store: MemoryStore) -> None:
    store.save(
        MemoryEntry(
            name="staged", description="d", body="b", type=MemoryType.PROJECT,
            scope=MemoryScope.GLOBAL, created=date(2026, 1, 1), state=MemoryState.PENDING,
        )
    )
    store.save(
        MemoryEntry(
            name="active", description="d", body="b", type=MemoryType.PROJECT,
            scope=MemoryScope.GLOBAL, created=date(2026, 1, 1),
        )
    )

    result = plan_memory_pending(store)

    assert [e.name for e in result] == ["staged"]


def test_plan_memory_hygiene_flags_dead_reference(store: MemoryStore) -> None:
    store.save(
        MemoryEntry(
            name="dead-dash", description="d", body="/no/such/path.md",
            type=MemoryType.REFERENCE, scope=MemoryScope.GLOBAL, created=date(2026, 7, 4),
        )
    )

    result = plan_memory_hygiene(store, now=date(2026, 7, 5))

    assert [c.name for c in result] == ["dead-dash"]
    assert result[0].reason == "dead-reference"


def test_plan_memory_hygiene_excludes_boundary(store: MemoryStore) -> None:
    store.save(
        MemoryEntry(
            name="prod-gate", description="d", body="b",
            type=MemoryType.BOUNDARY, scope=MemoryScope.GLOBAL, created=date(2025, 1, 1),
        )
    )

    result = plan_memory_hygiene(store, now=date(2026, 7, 5))

    assert result == []
