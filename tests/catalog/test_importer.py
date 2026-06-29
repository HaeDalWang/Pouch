"""vendored-import v0 계약 검증.

핵심 3계약:
  ① body가 pouch에 복사/저장되지 않는다 (upstream 참조만)
  ② overlay에 쓴 게 body(=upstream 원본)를 안 건드린다 (분리 보장)
  ③ 재import해도 overlay가 안 날아간다 (재import 멱등)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.importer import apply_overlay, import_vendored_skill, read_skill
from pouch.catalog.model import Overlay, Ownership, ToolKind
from pouch.catalog.store import CatalogStore

# 본문에만 등장하는 표식 — 카탈로그에 새면 안 된다.
_BODY_MARKER = "VERIFIED_EDGE_CASE_BODY_MARKER"

_SKILL_MD = f"""---
name: aws-iam
description: IAM에서 에이전트가 자주 틀리는 검증된 교정 사항
version: 1
---

# AWS IAM — Common Pitfalls

{_BODY_MARKER}

## Verified Edge Cases
정책 평가 엣지 케이스...
"""


@pytest.fixture
def skill_md(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "src" / "aws-iam"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    path.write_text(_SKILL_MD, encoding="utf-8")
    return path


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(catalog_dir=tmp_path / "catalog")


def test_read_skill_extracts_frontmatter_not_body(skill_md: Path) -> None:
    # Act
    src = read_skill(skill_md, upstream="aws/.../aws-iam")

    # Assert
    assert src.id == "aws-iam"
    assert "IAM" in src.description
    assert src.upstream == "aws/.../aws-iam"


def test_contract1_body_not_stored(skill_md: Path, store: CatalogStore, tmp_path: Path) -> None:
    # Act
    entry = import_vendored_skill(skill_md, store, upstream="aws/.../aws-iam", synced_at="2026-06-29")

    # Assert — 엔트리에도, 디스크 파일에도 본문이 없다
    assert entry.ownership is Ownership.VENDORED
    assert entry.body is None
    saved = (tmp_path / "catalog" / "aws-iam.md").read_text(encoding="utf-8")
    assert _BODY_MARKER not in saved
    assert entry.upstream == "aws/.../aws-iam"


def test_contract2_overlay_does_not_touch_body(
    skill_md: Path, store: CatalogStore
) -> None:
    # Arrange
    import_vendored_skill(skill_md, store, upstream="aws/.../aws-iam", synced_at="2026-06-29")
    source_before = skill_md.read_text(encoding="utf-8")

    # Act — overlay에 개인화를 쓴다
    updated = apply_overlay(
        store, "aws-iam", Overlay(boundaries=("prod-gate",), notes="prod는 확인")
    )

    # Assert — overlay는 붙되 body는 여전히 없고, upstream 원본은 한 글자도 안 바뀜
    assert updated.overlay.boundaries == ("prod-gate",)
    assert updated.body is None
    assert skill_md.read_text(encoding="utf-8") == source_before


def test_contract3_reimport_preserves_overlay(
    skill_md: Path, store: CatalogStore
) -> None:
    # Arrange — import 후 overlay 작성
    import_vendored_skill(skill_md, store, upstream="aws/.../aws-iam", synced_at="2026-06-29")
    apply_overlay(store, "aws-iam", Overlay(boundaries=("prod-gate",), notes="내 메모"))

    # Act — 같은 걸 다시 import (upstream 갱신 시뮬레이션)
    reimported = import_vendored_skill(
        skill_md, store, upstream="aws/.../aws-iam", synced_at="2026-07-01"
    )

    # Assert — overlay 보존, synced_at은 갱신
    assert reimported.overlay.boundaries == ("prod-gate",)
    assert reimported.overlay.notes == "내 메모"
    assert reimported.synced_at == "2026-07-01"


def test_reimport_is_still_skill_kind(skill_md: Path, store: CatalogStore) -> None:
    entry = import_vendored_skill(skill_md, store, upstream="u", synced_at="2026-06-29")
    assert entry.kind is ToolKind.SKILL
