"""owned-import v0 계약 검증 — vendored의 거울상.

vendored는 "본문은 남의 것 → 저장 안 함, upstream 추적, 재import는 overlay 보존".
owned는 정반대다:
  ① body를 통째로 소유한다 (카탈로그 파일에 본문이 들어있어야 한다)
  ② upstream을 끊는다 (입양 = 디커플, 더는 남을 추적하지 않는다)
  ③ 재import가 내가 깎은 body를 말없이 덮지 않는다 (force=True만 강제)
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pouch.catalog.importer import import_owned_skill
from pouch.catalog.model import Ownership, ToolKind
from pouch.catalog.store import CatalogStore

# 본문에만 등장하는 표식 — owned는 이게 카탈로그에 "있어야" 한다(vendored와 반대).
_BODY_MARKER = "OWNED_BODY_MUST_BE_KEPT"

_SKILL_MD = f"""---
name: my-workflow
description: 내가 입양해 직접 깎아 쓸 워크플로
version: 1
---

# My Workflow

{_BODY_MARKER}

## Steps
실제 절차 본문...
"""


@pytest.fixture
def skill_md(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "src" / "my-workflow"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    path.write_text(_SKILL_MD, encoding="utf-8")
    return path


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(catalog_dir=tmp_path / "catalog")


def test_contract1_body_is_owned(skill_md: Path, store: CatalogStore, tmp_path: Path) -> None:
    # Act
    entry = import_owned_skill(skill_md, store, source="ecc")

    # Assert — 엔트리에도, 디스크 파일에도 본문이 통째로 들어있다(vendored와 반대)
    assert entry.ownership is Ownership.OWNED
    assert entry.body is not None
    assert _BODY_MARKER in entry.body
    saved = (tmp_path / "catalog" / "my-workflow.md").read_text(encoding="utf-8")
    assert _BODY_MARKER in saved


def test_contract2_upstream_is_severed(skill_md: Path, store: CatalogStore) -> None:
    # Act
    entry = import_owned_skill(skill_md, store, source="ecc")

    # Assert — 입양은 추적을 끊는다. upstream/synced_at/overlay 전부 없다.
    assert entry.upstream is None
    assert entry.synced_at is None
    assert entry.overlay is None


def test_contract3_reimport_refuses_to_clobber_carved_body(
    skill_md: Path, store: CatalogStore
) -> None:
    # Arrange — import 후 내가 body를 직접 깎는다(진화)
    import_owned_skill(skill_md, store, source="ecc")
    carved = replace(store.get("my-workflow"), body="# 내가 새로 쓴 본문\n오롯이 내 것")
    store.save(carved)

    # Act & Assert — 그냥 재import하면 내 수정을 덮으려 하므로 거부한다
    with pytest.raises(FileExistsError):
        import_owned_skill(skill_md, store, source="ecc")

    # 내 body는 그대로 살아있다
    assert store.get("my-workflow").body == "# 내가 새로 쓴 본문\n오롯이 내 것"


def test_contract3_force_overwrites(skill_md: Path, store: CatalogStore) -> None:
    # Arrange
    import_owned_skill(skill_md, store, source="ecc")
    store.save(replace(store.get("my-workflow"), body="덮어써질 본문"))

    # Act — force=True면 명시적으로 upstream 본문으로 되돌린다
    reimported = import_owned_skill(skill_md, store, source="ecc", force=True)

    # Assert
    assert _BODY_MARKER in reimported.body


def test_owned_skill_kind(skill_md: Path, store: CatalogStore) -> None:
    entry = import_owned_skill(skill_md, store, source="ecc")
    assert entry.kind is ToolKind.SKILL


def test_owned_tags_carried(skill_md: Path, store: CatalogStore) -> None:
    entry = import_owned_skill(skill_md, store, source="ecc", tags=("mine", "wf"))
    assert entry.has_tag("mine")
    assert entry.has_tag("wf")
