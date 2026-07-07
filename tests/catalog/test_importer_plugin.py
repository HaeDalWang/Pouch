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


def test_plugin_mcp_gets_runtime_alias_and_plugin_surface(
    plugin_dir: Path, store: CatalogStore
) -> None:
    # Claude Code는 플러그인 MCP 서버를 plugin_<이름>_<서버>로 노출한다.
    # 이름은 .claude-plugin/plugin.json에서 읽는다(디렉토리명 추측 금지).
    from pouch.catalog.model import SURFACE_PLUGIN

    import_plugin(plugin_dir, store, synced_at="2026-07-03")

    mcp = store.get("aws-mcp")
    assert mcp is not None
    assert "plugin_aws-core_aws-mcp" in mcp.aliases
    assert mcp.surface == SURFACE_PLUGIN  # 표면은 플러그인이 관리 — pouch는 관측만


def test_direct_mcp_import_is_pouch_surfaced(tmp_path: Path, store: CatalogStore) -> None:
    # .mcp.json을 직접 들이면 표면을 pouch가 관리한다 — alias도 필요 없다.
    from pouch.catalog.importer import import_mcp_servers

    path = tmp_path / ".mcp.json"
    path.write_text(_MCP_JSON, encoding="utf-8")

    entries = import_mcp_servers(path, store, source="me")

    assert entries[0].aliases == ()
    assert entries[0].surface is None


# --- 커버리지 갭: plugin이 commands/·agents/도 원자로 분해해야 한다 (ECC 구조) ---

_AGENT_MD = """---
name: code-reviewer
description: 코드 품질·보안 리뷰 에이전트
tools: ["Read", "Grep"]
---

# Reviewer
에이전트 본문 — 카탈로그에 새면 안 된다.
"""

_COMMAND_MD = """---
description: 두 리뷰어가 모두 통과해야 배포하는 수렴 루프
---

# Santa Loop
명령 본문 — 카탈로그에 새면 안 된다.
"""


@pytest.fixture
def full_plugin_dir(tmp_path: Path) -> Path:
    """ECC 구조를 본뜬 plugin: skills + commands + agents (mcp 없음)."""
    root = tmp_path / "plugin" / "ecc"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "ecc", "version": "2.0.0"}', encoding="utf-8"
    )
    sdir = root / "skills" / "tdd-workflow"
    sdir.mkdir(parents=True)
    (sdir / "SKILL.md").write_text(_skill_md("tdd-workflow"), encoding="utf-8")
    (root / "commands").mkdir()
    (root / "commands" / "santa-loop.md").write_text(_COMMAND_MD, encoding="utf-8")
    (root / "agents").mkdir()
    (root / "agents" / "reviewer-file.md").write_text(_AGENT_MD, encoding="utf-8")
    return root


def test_plugin_decomposes_commands_and_agents(
    full_plugin_dir: Path, store: CatalogStore
) -> None:
    # Act
    result = import_plugin(full_plugin_dir, store, synced_at="2026-07-07")

    # Assert — skill + command(파일명 id) + agent(name 필드 id) 셋 다 원자로.
    by_id = {e.id: e for e in result.entries}
    assert by_id["tdd-workflow"].kind is ToolKind.SKILL
    assert by_id["santa-loop"].kind is ToolKind.COMMAND  # 파일명 stem
    assert "code-reviewer" in by_id  # agent는 name 필드(파일명 reviewer-file 아님)
    assert by_id["code-reviewer"].kind is ToolKind.AGENT
    # 셋 다 vendored, body 안 들임
    assert all(by_id[i].ownership is Ownership.VENDORED for i in by_id)
    assert all(by_id[i].body is None for i in by_id)


def test_plugin_broken_command_skipped_loudly(
    full_plugin_dir: Path, store: CatalogStore
) -> None:
    # 명령은 파일명이 id라 name이 없어도 안 깨진다 — 하지만 파싱 자체가 깨진
    # 파일은 건너뛰되 보고한다(스킬과 같은 격리 원칙).
    bad = full_plugin_dir / "commands" / "broken.md"
    bad.write_text("---\n: : : 깨진 yaml : :\n---\n본문", encoding="utf-8")

    result = import_plugin(full_plugin_dir, store, synced_at="2026-07-07")

    # 성한 것들은 담기고, 깨진 하나만 skipped로 보고된다
    assert "santa-loop" in {e.id for e in result.entries}
    assert any("broken" in s.path for s in result.skipped)


_RULE_MD = """---
paths: ["**/*.py"]
---

# Python Coding Style
규칙 본문.
"""


def test_plugin_decomposes_rules_with_scoped_ids(
    full_plugin_dir: Path, store: CatalogStore
) -> None:
    # 계층 규칙(python/·common/)이 부모 스코프 id로 원자 분해된다.
    # 최상위 rules/README.md는 규칙이 아니라 구조 설명서라 담기지 않는다.
    for lang in ("python", "common"):
        rdir = full_plugin_dir / "rules" / lang
        rdir.mkdir(parents=True)
        (rdir / "coding-style.md").write_text(_RULE_MD, encoding="utf-8")
    (full_plugin_dir / "rules" / "README.md").write_text("# Rules\n구조 설명", encoding="utf-8")

    result = import_plugin(full_plugin_dir, store, synced_at="2026-07-07")

    ids = {e.id for e in result.entries}
    assert "python__coding-style" in ids
    assert "common__coding-style" in ids
    assert "README" not in ids  # 최상위 문서는 규칙 아님(한 겹 glob이 걸러냄)
    rule_entries = [e for e in result.entries if e.kind is ToolKind.RULE]
    assert all(e.ownership is Ownership.VENDORED for e in rule_entries)
