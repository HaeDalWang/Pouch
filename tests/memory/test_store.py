"""메모리 저장소 CRUD 및 스코프 경로 검증."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState, MemoryType
from pouch.memory.store import MemoryStore


def _entry(name: str, scope: MemoryScope = MemoryScope.GLOBAL) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=f"{name} 설명",
        body=f"{name} 본문",
        type=MemoryType.PROJECT,
        scope=scope,
        created=date(2026, 6, 27),
    )


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(
        global_dir=tmp_path / "global",
        project_dir=tmp_path / "project",
    )


def test_save_then_get_returns_same_entry(store: MemoryStore) -> None:
    # Arrange
    entry = _entry("alpha")

    # Act
    store.save(entry)
    loaded = store.get("alpha", MemoryScope.GLOBAL)

    # Assert
    assert loaded == entry


def test_save_writes_file_to_scope_dir(store: MemoryStore, tmp_path: Path) -> None:
    # Arrange / Act
    store.save(_entry("beta", MemoryScope.PROJECT))

    # Assert
    assert (tmp_path / "project" / "beta.md").exists()
    assert not (tmp_path / "global" / "beta.md").exists()


def test_list_merges_global_and_project(store: MemoryStore) -> None:
    # Arrange
    store.save(_entry("g", MemoryScope.GLOBAL))
    store.save(_entry("p", MemoryScope.PROJECT))

    # Act
    names = {e.name for e in store.list()}

    # Assert
    assert names == {"g", "p"}


def test_forget_removes_file(store: MemoryStore) -> None:
    # Arrange
    store.save(_entry("gone"))

    # Act
    removed = store.forget("gone", MemoryScope.GLOBAL)

    # Assert
    assert removed is True
    assert store.get("gone", MemoryScope.GLOBAL) is None


def test_forget_missing_returns_false(store: MemoryStore) -> None:
    # Act / Assert
    assert store.forget("nope", MemoryScope.GLOBAL) is False


def test_save_is_idempotent_overwrites_same_name(store: MemoryStore) -> None:
    # Arrange
    store.save(_entry("dup"))
    updated = MemoryEntry(
        name="dup",
        description="새 설명",
        body="새 본문",
        type=MemoryType.USER,
        scope=MemoryScope.GLOBAL,
        created=date(2026, 6, 27),
    )

    # Act
    store.save(updated)

    # Assert
    assert store.get("dup", MemoryScope.GLOBAL) == updated
    assert len(list(store.list())) == 1


def test_promote_sets_indexed_and_updates_index(store: MemoryStore, tmp_path: Path) -> None:
    # Arrange — pending은 재인덱싱 시 인덱스에서 제외돼야 한다
    pending = MemoryEntry(
        name="staged", description="d", body="b",
        type=MemoryType.PROJECT, scope=MemoryScope.GLOBAL,
        created=date(2026, 6, 27), state=MemoryState.PENDING,
    )
    store.save(pending)

    # Act
    promoted = store.promote(pending)

    # Assert
    assert promoted.state is MemoryState.INDEXED
    assert store.get("staged", MemoryScope.GLOBAL).state is MemoryState.INDEXED
    index = (tmp_path / "global" / "MEMORY.md").read_text(encoding="utf-8")
    assert "staged" in index


def test_demote_sets_archived_and_removes_from_index(store: MemoryStore, tmp_path: Path) -> None:
    # Arrange
    entry = _entry("aging")
    store.save(entry)

    # Act
    demoted = store.demote(entry)

    # Assert — 파일은 남고(archived), 인덱스에선 빠진다("떨어진다 ≠ 삭제된다"의 기억판)
    assert demoted.state is MemoryState.ARCHIVED
    assert store.get("aging", MemoryScope.GLOBAL).state is MemoryState.ARCHIVED
    index = (tmp_path / "global" / "MEMORY.md").read_text(encoding="utf-8")
    assert "aging" not in index
