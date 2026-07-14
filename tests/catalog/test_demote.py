"""demote — 카탈로그 항목을 소스 스테이징으로 강등(진입→가리키기, promote의 거울상).

관문 (다)의 뒷문: promote가 "소스→카탈로그 진입"이라면 demote는 그 역이다 —
안 쓰는 도구를 카탈로그에서 소스로 되돌린다. promote와 달리 이건 진짜 *이동*이라
카탈로그 원본을 지운다("그대로 옮기기": 파일 이동만, overlay 보존). 194
마이그레이션(옛 import가 카탈로그에 직행시킨 안 쓴 도구들)이 이 연산으로 정리된다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.demote import demote
from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore


@pytest.fixture
def stores(tmp_path: Path) -> tuple[CatalogStore, CatalogStore]:
    source = CatalogStore(catalog_dir=tmp_path / "sources")
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    return source, catalog


def _skill(entry_id: str, *, overlay: Overlay | None = None) -> ToolEntry:
    return ToolEntry.vendored(
        id=entry_id, kind=ToolKind.SKILL, source="ecc",
        title=entry_id, description="d", upstream=f"/up/{entry_id}",
        synced_at="2026-07-13T00:00:00", overlay=overlay,
    )


def test_demote_moves_catalog_entry_to_source(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange — 카탈로그에만 있고 소스엔 없다(옛 import가 직행시킨 상태).
    source, catalog = stores
    catalog.save(_skill("unused"))
    assert source.get("unused") is None

    # Act
    result = demote("unused", source_store=source, catalog_store=catalog)

    # Assert — 소스로 옮겨졌고 반환값도 그 엔트리.
    assert result is not None
    assert result.id == "unused"
    assert source.get("unused") is not None


def test_demote_removes_from_catalog(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange
    source, catalog = stores
    catalog.save(_skill("unused"))

    # Act
    demote("unused", source_store=source, catalog_store=catalog)

    # Assert — 카탈로그에선 사라진다(promote와 다른 지점: 진짜 이동).
    assert catalog.get("unused") is None


def test_demote_preserves_overlay(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange — 진입 후 쌓인 개인화(overlay)가 있다.
    source, catalog = stores
    catalog.save(_skill("unused", overlay=Overlay(tags=("mine",), notes="개인 메모")))

    # Act — "그대로 옮기기": overlay까지 실어 소스로.
    result = demote("unused", source_store=source, catalog_store=catalog)

    # Assert — 개인화가 소스본에 보존된다(강등해도 안 잃음, 재진입 시 되살아남).
    assert result is not None
    assert source.get("unused").overlay is not None
    assert source.get("unused").overlay.notes == "개인 메모"


def test_demote_missing_catalog_returns_none(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Act / Assert — 카탈로그에 없으면 강등할 게 없다(멱등 — 재실행 안전).
    source, catalog = stores
    assert demote("ghost", source_store=source, catalog_store=catalog) is None


def test_demote_reverses_promote(
    stores: tuple[CatalogStore, CatalogStore]
) -> None:
    # Arrange — 소스→카탈로그 진입(promote)된 상태를 만든다.
    from pouch.catalog.promote import promote

    source, catalog = stores
    source.save(_skill("exa"))
    promote("exa", source_store=source, catalog_store=catalog)
    assert catalog.get("exa") is not None

    # Act — 강등하면
    demote("exa", source_store=source, catalog_store=catalog)

    # Assert — 카탈로그에서 내려가고 소스엔 남는다(왕복 대칭).
    assert catalog.get("exa") is None
    assert source.get("exa") is not None
