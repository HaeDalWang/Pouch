"""sync 계약 검증 — vendored upstream 갱신을 카탈로그에 반영한다.

sync는 import의 역방향이 아니라 '재방문'이다. 카탈로그에 이미 있는 vendored
엔트리들의 upstream을 다시 읽어 최신 metadata로 맞춘다:
  ① vendored만 sync한다 (owned=upstream 없음, linked=외부 — 둘 다 건너뜀)
  ② upstream이 바뀌면 metadata(description 등)가 갱신된다
  ③ overlay는 보존된다 (개인화는 upstream 갱신에 안 쓸려나감)
  ④ synced_at이 갱신된다
  ⑤ upstream 파일이 사라졌으면 조용히 삼키지 않고 결과로 보고한다
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.importer import apply_overlay, import_vendored_skill
from pouch.catalog.model import Overlay, Ownership, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.catalog.sync import sync_all, sync_entry


def _skill_md(name: str, description: str, body: str = "본문 절차...") -> str:
    return f"""---
name: {name}
description: {description}
version: 1
---

# {name}

{body}
"""


@pytest.fixture
def upstream_skill(tmp_path: Path) -> Path:
    sdir = tmp_path / "upstream" / "aws-iam"
    sdir.mkdir(parents=True)
    path = sdir / "SKILL.md"
    path.write_text(_skill_md("aws-iam", "원래 설명"), encoding="utf-8")
    return path


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(catalog_dir=tmp_path / "catalog")


def test_contract2_metadata_refreshed_on_upstream_change(
    upstream_skill: Path, store: CatalogStore
) -> None:
    # Arrange — import 후 upstream이 갱신됨
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    upstream_skill.write_text(_skill_md("aws-iam", "갱신된 설명"), encoding="utf-8")

    # Act
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")

    # Assert
    assert result.description == "갱신된 설명"
    assert store.get("aws-iam").description == "갱신된 설명"


def test_contract3_overlay_preserved(upstream_skill: Path, store: CatalogStore) -> None:
    # Arrange
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    apply_overlay(store, "aws-iam", Overlay(boundaries=("prod-gate",), notes="내 메모"))
    upstream_skill.write_text(_skill_md("aws-iam", "갱신된 설명"), encoding="utf-8")

    # Act
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")

    # Assert — upstream 갱신돼도 내 overlay는 그대로
    assert result.overlay.boundaries == ("prod-gate",)
    assert result.overlay.notes == "내 메모"


def test_contract4_synced_at_updated(upstream_skill: Path, store: CatalogStore) -> None:
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")
    assert result.synced_at == "2026-07-05"


def test_contract5_missing_upstream_reported_not_swallowed(
    upstream_skill: Path, store: CatalogStore
) -> None:
    # Arrange — import 후 upstream이 사라짐
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    upstream_skill.unlink()

    # Act & Assert — 조용히 삼키지 않고 명확히 실패
    with pytest.raises(FileNotFoundError):
        sync_entry(store, "aws-iam", synced_at="2026-07-05")


def test_contract1_sync_all_skips_owned_and_linked(
    upstream_skill: Path, store: CatalogStore
) -> None:
    # Arrange — vendored 1 + owned 1 + linked 1
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    store.save(
        ToolEntry.owned(
            id="my-wf", kind=ToolKind.SKILL, source="me", title="내 워크플로",
            description="owned", body="내 본문",
        )
    )
    store.save(
        ToolEntry.linked(
            id="aws-mcp", kind=ToolKind.MCP, source="aws", title="aws-mcp",
            description="linked", recipe={"command": "uvx", "args": []},
        )
    )
    upstream_skill.write_text(_skill_md("aws-iam", "갱신된 설명"), encoding="utf-8")

    # Act
    synced = sync_all(store, synced_at="2026-07-05")

    # Assert — vendored만 sync. owned·linked는 손도 안 댐.
    assert [e.id for e in synced] == ["aws-iam"]
    assert store.get("my-wf").body == "내 본문"
    assert store.get("aws-mcp").ownership is Ownership.LINKED


def test_sync_entry_rejects_non_vendored(store: CatalogStore) -> None:
    store.save(
        ToolEntry.owned(
            id="my-wf", kind=ToolKind.SKILL, source="me", title="t",
            description="d", body="b",
        )
    )
    with pytest.raises(ValueError):
        sync_entry(store, "my-wf", synced_at="2026-07-05")
