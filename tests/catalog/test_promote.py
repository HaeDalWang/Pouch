"""promote — 소스 스테이징의 항목을 카탈로그로 진입시킨다(가리키기→진입).

관문 (다)의 코어: import는 소스에만 담고(진입 0), 실사용·install·세트가 진입시킨다.
promote는 "소스에 있는 걸 카탈로그로 옮긴다"는 그 진입의 유일한 원자 연산이다.
소스에서는 지우지 않는다(백과사전 페이지는 남고 노트에 옮긴 것만 카탈로그).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.catalog.promote import promote
from pouch.catalog.store import CatalogStore


@pytest.fixture
def stores(tmp_path: Path) -> tuple[CatalogStore, CatalogStore]:
    source = CatalogStore(catalog_dir=tmp_path / "sources")
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    return source, catalog


def _skill(entry_id: str, *, overlay: Overlay | None = None) -> ToolEntry:
    entry = ToolEntry.vendored(
        id=entry_id, kind=ToolKind.SKILL, source="ecc",
        title=entry_id, description="d", upstream=f"/up/{entry_id}",
        synced_at="2026-07-13T00:00:00", overlay=overlay,
    )
    return entry


def test_promote_copies_source_entry_into_catalog(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange — 소스에만 있고 카탈로그엔 없다.
    source, catalog = stores
    source.save(_skill("exa"))
    assert catalog.get("exa") is None

    # Act
    result = promote("exa", source_store=source, catalog_store=catalog)

    # Assert — 카탈로그에 진입, 반환값도 그 엔트리.
    assert result is not None
    assert result.id == "exa"
    assert catalog.get("exa") is not None


def test_promote_does_not_remove_from_source(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange
    source, catalog = stores
    source.save(_skill("exa"))

    # Act
    promote("exa", source_store=source, catalog_store=catalog)

    # Assert — 소스에 그대로 남는다(백과사전 페이지는 안 지운다).
    assert source.get("exa") is not None


def test_promote_preserves_kind_and_ownership(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange — linked(mcp) 관측 스텁이 소스에 있다.
    source, catalog = stores
    stub = ToolEntry.linked(
        id="aws-mcp", kind=ToolKind.MCP, source="ecc",
        title="aws", description="d", recipe={}, surface="plugin",
        aliases=("plugin_ecc_aws-mcp",),
    )
    source.save(stub)

    # Act
    result = promote("aws-mcp", source_store=source, catalog_store=catalog)

    # Assert — kind·ownership·surface·alias 그대로 진입.
    assert result is not None
    assert result.kind is ToolKind.MCP
    assert result.ownership.value == "linked"
    assert result.surface == "plugin"
    assert result.aliases == ("plugin_ecc_aws-mcp",)


def test_promote_missing_source_returns_none(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Act / Assert — 소스에 없는 건 진입시킬 게 없다.
    source, catalog = stores
    assert promote("ghost", source_store=source, catalog_store=catalog) is None


def test_promote_is_idempotent_and_does_not_clobber_catalog_overlay(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange — 이미 카탈로그에 진입해 개인화(overlay)가 쌓였다. 소스본엔 overlay 없음.
    source, catalog = stores
    source.save(_skill("exa"))
    catalog.save(_skill("exa", overlay=Overlay(tags=("mine",), notes="개인 메모")))

    # Act — 다시 promote해도
    result = promote("exa", source_store=source, catalog_store=catalog)

    # Assert — 카탈로그의 개인화를 소스본으로 뭉개지 않는다(멱등, 진입 후 쌓인 것 보존).
    assert result is not None
    assert result.overlay is not None
    assert result.overlay.notes == "개인 메모"
    assert catalog.get("exa").overlay.notes == "개인 메모"
