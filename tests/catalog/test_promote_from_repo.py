"""저장소 → 카탈로그 진입 — Phase 4.8 조각 ④의 관문 절반.

`pouch catalog install <저장소>/<도구>`가 색인의 항목을 카탈로그로 진입시킨다.
진입 원칙은 promote와 같다("진입은 항상 이 한 파일을 거친다"):

  - 카탈로그 안 정체는 맨 이름(`pulumi`) — 장부는 평면이라 "/"를 못 담고,
    출처는 upstream(클론 안 경로)이 이미 말한다
  - 같은 이름이 이미 딴 데서 와 있으면 정직하게 거부(조용한 덮어쓰기 금지)
  - 같은 출처면 재진입은 기존 항목 유지(개인화 overlay 보존 — 재설치 경로)
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.catalog.promote import promote_from_repo
from pouch.catalog.store import CatalogStore
from pouch.repos.index import index_repo


def _clone_with_skill(root: Path, name: str = "deploy-helper") -> Path:
    d = root / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: deploy tool\n---\n\n# 본문\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def index_root(tmp_path: Path) -> Path:
    clone = _clone_with_skill(tmp_path / "clone")
    root = tmp_path / "repo-index"
    index_repo("team", clone, index_dir=root / "team", synced_at="s")
    return root


def test_scoped_id_enters_the_catalog_under_its_bare_name(
    index_root: Path, tmp_path: Path
) -> None:
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")

    entry = promote_from_repo(
        "team/deploy-helper", index_root=index_root, catalog_store=catalog
    )

    assert entry is not None
    assert entry.id == "deploy-helper"
    assert catalog.get("deploy-helper") is not None


def test_unknown_scoped_id_returns_none(index_root: Path, tmp_path: Path) -> None:
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")

    assert promote_from_repo("team/ghost", index_root=index_root, catalog_store=catalog) is None
    assert promote_from_repo("nope/deploy-helper", index_root=index_root, catalog_store=catalog) is None


def test_an_unscoped_id_is_not_this_doors_business(index_root: Path, tmp_path: Path) -> None:
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")

    assert promote_from_repo("deploy-helper", index_root=index_root, catalog_store=catalog) is None


def test_a_name_taken_by_a_different_origin_is_refused(
    index_root: Path, tmp_path: Path
) -> None:
    """딴 데서 온 같은 이름을 조용히 덮지 않는다."""
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    catalog.save(ToolEntry.owned(
        id="deploy-helper", kind=ToolKind.SKILL, source="me",
        title="내가 만든 것", description="d", body="본문",
    ))

    with pytest.raises(ValueError, match="이미"):
        promote_from_repo("team/deploy-helper", index_root=index_root, catalog_store=catalog)


def test_re_entry_from_the_same_origin_keeps_personalization(
    index_root: Path, tmp_path: Path
) -> None:
    """재설치 경로 — 같은 출처의 재진입은 기존 항목(개인화 포함)을 유지한다."""
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    first = promote_from_repo(
        "team/deploy-helper", index_root=index_root, catalog_store=catalog
    )
    assert first is not None
    catalog.save(replace(first, overlay=Overlay(tags=("mine",))))

    again = promote_from_repo(
        "team/deploy-helper", index_root=index_root, catalog_store=catalog
    )

    assert again is not None
    assert again.overlay is not None and "mine" in again.overlay.tags
