"""plugin 분해 계약 검증 — plugin은 ownership이 아니라 '번들'이다.

importer는 plugin을 원자 단위로 쪼갠다:
  ① plugin 자체는 카탈로그에 남지 않는다 (plugin이라는 엔트리/ownership 없음)
  ② .mcp.json의 각 서버 → linked (recipe+region, 외부 실행 위임)
  ③ skills/*/SKILL.md → 각각 vendored (body 안 들임, upstream 추적)
  ④ 재import는 vendored 스킬의 overlay를 보존한다 (import_vendored_skill 위임)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.importer import apply_overlay, import_plugin
from pouch.catalog.model import Overlay, Ownership, ToolKind
from pouch.catalog.store import CatalogStore

# 스킬 본문에만 등장하는 표식 — vendored이므로 카탈로그에 새면 안 된다.
_BODY_MARKER = "PLUGIN_SKILL_BODY_MUST_NOT_LEAK"

_MCP_JSON = """{
  "mcpServers": {
    "aws-mcp": {
      "command": "uvx",
      "args": [
        "mcp-proxy-for-aws@latest",
        "https://aws-mcp.us-east-1.api.aws/mcp"
      ]
    }
  }
}
"""

_PLUGIN_JSON = """{
  "name": "aws-core",
  "version": "1.0.0",
  "description": "AWS toolkit bundle"
}
"""


def _skill_md(name: str) -> str:
    return f"""---
name: {name}
description: {name} 검증된 절차
version: 1
---

# {name}

{_BODY_MARKER}

본문 절차...
"""


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """실제 aws-core 구조를 본뜬 합성 plugin: .mcp.json + skills/*/SKILL.md."""
    root = tmp_path / "plugin" / "aws-core"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(_PLUGIN_JSON, encoding="utf-8")
    (root / ".mcp.json").write_text(_MCP_JSON, encoding="utf-8")
    for skill in ("aws-iam", "aws-cdk"):
        sdir = root / "skills" / skill
        sdir.mkdir(parents=True)
        (sdir / "SKILL.md").write_text(_skill_md(skill), encoding="utf-8")
    return root


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(catalog_dir=tmp_path / "catalog")


def test_contract1_no_plugin_entry(plugin_dir: Path, store: CatalogStore) -> None:
    # Act
    result = import_plugin(plugin_dir, store, synced_at="2026-06-30")

    # Assert — plugin 자체는 엔트리로 남지 않는다. 원자(skill 2 + mcp 1)만.
    ids = {e.id for e in result.entries}
    assert "aws-core" not in ids
    assert ids == {"aws-iam", "aws-cdk", "aws-mcp"}
    # 카탈로그에 plugin kind/ownership 같은 건 존재하지 않는다
    assert all(e.kind in {ToolKind.SKILL, ToolKind.MCP} for e in store.list())


def test_broken_skill_is_skipped_loudly_not_fatally(
    plugin_dir: Path, store: CatalogStore
) -> None:
    # 실측(ECC, 2026-07-02): 182개 중 1개가 name 없는 SKILL.md — 그 하나가
    # 전체 import를 죽였다. 깨진 조각은 건너뛰되 이유와 함께 보고하고,
    # 성한 조각은 담는다(java 감지와 같은 원칙: 추측한 식별자를 넣지 않는다).
    broken = plugin_dir / "skills" / "broken-skill"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text(
        "---\ndescription: name이 없다\n---\n본문", encoding="utf-8"
    )

    result = import_plugin(plugin_dir, store, synced_at="2026-06-30")

    assert {e.id for e in result.entries} == {"aws-iam", "aws-cdk", "aws-mcp"}
    assert len(result.skipped) == 1
    assert "broken-skill" in result.skipped[0].path
    assert "name" in result.skipped[0].reason
    assert store.get("broken-skill") is None  # 추측 식별자로 담지 않는다


def test_contract2_mcp_becomes_linked(plugin_dir: Path, store: CatalogStore) -> None:
    # Act
    import_plugin(plugin_dir, store, synced_at="2026-06-30")

    # Assert — .mcp.json 서버는 linked. recipe에 실행법, region 파싱.
    mcp = store.get("aws-mcp")
    assert mcp is not None
    assert mcp.ownership is Ownership.LINKED
    assert mcp.kind is ToolKind.MCP
    assert mcp.recipe == {
        "command": "uvx",
        "args": ["mcp-proxy-for-aws@latest", "https://aws-mcp.us-east-1.api.aws/mcp"],
    }
    assert mcp.region == "us-east-1"


def test_contract3_skills_are_vendored_no_body(
    plugin_dir: Path, store: CatalogStore, tmp_path: Path
) -> None:
    # Act
    import_plugin(plugin_dir, store, synced_at="2026-06-30")

    # Assert — 각 스킬은 vendored, body는 디스크에도 새지 않는다
    iam = store.get("aws-iam")
    assert iam.ownership is Ownership.VENDORED
    assert iam.body is None
    saved = (tmp_path / "catalog" / "aws-iam.md").read_text(encoding="utf-8")
    assert _BODY_MARKER not in saved
    # upstream은 실제 SKILL.md를 가리켜 sync가 다시 읽을 수 있어야 한다
    assert "aws-iam" in iam.upstream


def test_contract4_reimport_preserves_skill_overlay(
    plugin_dir: Path, store: CatalogStore
) -> None:
    # Arrange — import 후 스킬에 overlay
    import_plugin(plugin_dir, store, synced_at="2026-06-30")
    apply_overlay(store, "aws-iam", Overlay(boundaries=("prod-gate",), notes="내 메모"))

    # Act — plugin 재import (upstream 갱신 시뮬레이션)
    import_plugin(plugin_dir, store, synced_at="2026-07-02")

    # Assert — overlay 보존, synced_at 갱신
    iam = store.get("aws-iam")
    assert iam.overlay.boundaries == ("prod-gate",)
    assert iam.overlay.notes == "내 메모"
    assert iam.synced_at == "2026-07-02"


def test_skills_carry_vendor_tag(plugin_dir: Path, store: CatalogStore) -> None:
    import_plugin(plugin_dir, store, synced_at="2026-06-30")
    assert store.get("aws-cdk").has_tag("vendor:aws")
