"""CatalogStore — 저장/조회/태그·ownership 검색 검증."""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.model import Ownership, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(catalog_dir=tmp_path / "catalog")


def _owned(entry_id: str, tags: tuple[str, ...] = ()) -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id, kind=ToolKind.SKILL, source="self",
        title=entry_id, description="d", body="b", tags=tags,
    )


def test_save_then_get(store: CatalogStore) -> None:
    entry = _owned("alpha")
    store.save(entry)
    assert store.get("alpha") == entry


def test_get_missing_returns_none(store: CatalogStore) -> None:
    assert store.get("nope") is None


def test_list_returns_all(store: CatalogStore) -> None:
    store.save(_owned("a"))
    store.save(_owned("b"))
    assert {e.id for e in store.list()} == {"a", "b"}


def test_search_by_tag_requires_all(store: CatalogStore) -> None:
    store.save(_owned("aws-dev", tags=("vendor:aws", "role:dev")))
    store.save(_owned("aws-only", tags=("vendor:aws",)))

    # vendor:aws AND role:dev → aws-dev만
    hits = store.search(tags=("vendor:aws", "role:dev"))
    assert {e.id for e in hits} == {"aws-dev"}


def test_search_by_ownership(store: CatalogStore) -> None:
    store.save(_owned("owned-one"))
    store.save(
        ToolEntry.linked(
            id="linked-one", kind=ToolKind.MCP, source="aws",
            title="t", description="d", recipe={"command": "x"},
        )
    )
    hits = store.search(ownership=Ownership.LINKED)
    assert {e.id for e in hits} == {"linked-one"}


def test_delete_removes_entry(store: CatalogStore) -> None:
    # migrate(강등)는 진짜 이동이라 카탈로그에서 지워야 한다 — drop과 다른 지점.
    store.save(_owned("gone"))
    assert store.delete("gone") is True
    assert store.get("gone") is None


def test_delete_missing_returns_false(store: CatalogStore) -> None:
    # 없는 걸 지우려 하면 조용히 False(멱등 — 재실행해도 터지지 않는다).
    assert store.delete("ghost") is False
