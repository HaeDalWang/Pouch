"""`pouch catalog` CLI 계약 검증 — Phase 4.6 ①: 공급 고리 연결.

  ① classify_source: 경로만 보고 plugin / skill / mcp-config를 판별(순수)
  ② import <SKILL.md>: 기본은 vendored(본문 안 들임, upstream 참조)
  ③ import --own: owned 입양 — 재실행은 거부, --force로만 덮는다
  ④ import <plugin dir>: 번들을 원자로 분해(linked + vendored)
  ⑤ list: 카탈로그 항목 + 표면 상태(active)를 보여준다
  ⑥ install <id>: 표면 배치 + state active — drop 후 재부착의 공식 입구
  ⑦ install <없는 id>: 명확히 실패(조용히 삼키지 않음)
  ⑧ sync: vendored의 synced_at 갱신, overlay 보존
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.catalog.commands import classify_source
from pouch.catalog.model import Overlay, Ownership
from pouch.catalog.store import CatalogStore
from pouch.cli import app

runner = CliRunner()

_SKILL_MD = "---\nname: aws-iam\ndescription: IAM 절차\n---\n\n# AWS IAM\n\nBODY\n"


@pytest.fixture
def skill_file(tmp_path: Path) -> Path:
    sdir = tmp_path / "upstream" / "aws-iam"
    sdir.mkdir(parents=True)
    path = sdir / "SKILL.md"
    path.write_text(_SKILL_MD, encoding="utf-8")
    return path


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / "some-plugin"
    (pdir / "skills" / "aws-iam").mkdir(parents=True)
    (pdir / "skills" / "aws-iam" / "SKILL.md").write_text(_SKILL_MD, encoding="utf-8")
    (pdir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"aws-mcp": {"command": "uvx", "args": ["x"]}}}),
        encoding="utf-8",
    )
    return pdir


# ── ① classify_source (순수) ─────────────────────────────────────────


def test_classify_plugin_dir_with_mcp_json(plugin_dir: Path) -> None:
    assert classify_source(plugin_dir) == "plugin"


def test_classify_plugin_dir_with_skills_only(tmp_path: Path) -> None:
    pdir = tmp_path / "p"
    (pdir / "skills").mkdir(parents=True)
    assert classify_source(pdir) == "plugin"


def test_classify_skill_md_file(skill_file: Path) -> None:
    assert classify_source(skill_file) == "skill"


def test_classify_dir_containing_skill_md(skill_file: Path) -> None:
    assert classify_source(skill_file.parent) == "skill"


def test_classify_mcp_json_file(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    path.write_text("{}", encoding="utf-8")
    assert classify_source(path) == "mcp"


def test_classify_unknown_raises(tmp_path: Path) -> None:
    unknown = tmp_path / "empty"
    unknown.mkdir()
    with pytest.raises(ValueError):
        classify_source(unknown)


# ── ②③④ import ──────────────────────────────────────────────────────


def test_contract2_import_skill_defaults_to_vendored(skill_file: Path) -> None:
    result = runner.invoke(app, ["catalog", "import", str(skill_file)])

    assert result.exit_code == 0
    entry = CatalogStore().get("aws-iam")
    assert entry is not None
    assert entry.ownership is Ownership.VENDORED
    assert entry.upstream == str(skill_file)


def test_contract3_import_own_adopts_and_refuses_overwrite(skill_file: Path) -> None:
    first = runner.invoke(app, ["catalog", "import", str(skill_file), "--own"])
    assert first.exit_code == 0
    entry = CatalogStore().get("aws-iam")
    assert entry is not None and entry.ownership is Ownership.OWNED
    assert entry.body and "BODY" in entry.body

    again = runner.invoke(app, ["catalog", "import", str(skill_file), "--own"])
    assert again.exit_code != 0  # 내가 깎은 body를 말없이 덮지 않는다

    forced = runner.invoke(
        app, ["catalog", "import", str(skill_file), "--own", "--force"]
    )
    assert forced.exit_code == 0


def test_contract4_import_plugin_decomposes(plugin_dir: Path) -> None:
    result = runner.invoke(app, ["catalog", "import", str(plugin_dir)])

    assert result.exit_code == 0
    store = CatalogStore()
    mcp = store.get("aws-mcp")
    skill = store.get("aws-iam")
    assert mcp is not None and mcp.ownership is Ownership.LINKED
    assert skill is not None and skill.ownership is Ownership.VENDORED


def test_import_with_tags(skill_file: Path) -> None:
    result = runner.invoke(
        app, ["catalog", "import", str(skill_file), "--tag", "stack:aws", "--tag", "iam"]
    )

    assert result.exit_code == 0
    entry = CatalogStore().get("aws-iam")
    assert entry is not None and set(entry.tags) == {"stack:aws", "iam"}


# ── ⑤ list ───────────────────────────────────────────────────────────


def test_contract5_list_shows_entries_and_surface(skill_file: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["catalog", "import", str(skill_file)])

    listed = runner.invoke(app, ["catalog", "list"])
    assert listed.exit_code == 0
    assert "aws-iam" in listed.output
    assert "vendored" in listed.output


def test_list_empty_catalog_guides(tmp_path: Path) -> None:
    result = runner.invoke(app, ["catalog", "list"])

    assert result.exit_code == 0
    assert "import" in result.output  # 빈 주머니면 채우는 법을 알려준다


# ── ⑥⑦ install ───────────────────────────────────────────────────────


def test_contract6_install_places_skill_and_marks_active(
    skill_file: Path, tmp_path: Path, monkeypatch
) -> None:
    runner.invoke(app, ["catalog", "import", str(skill_file)])
    skills_dir = tmp_path / "skills"

    result = runner.invoke(
        app,
        ["catalog", "install", "aws-iam", "--skills-dir", str(skills_dir),
         "--mcp-config", str(tmp_path / ".mcp.json")],
    )

    assert result.exit_code == 0
    assert (skills_dir / "aws-iam" / "SKILL.md").exists()
    from pouch.evolution.state import active_entries

    assert "aws-iam" in active_entries()


def test_contract7_install_unknown_id_fails_loudly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["catalog", "install", "ghost", "--skills-dir", str(tmp_path / "s"),
         "--mcp-config", str(tmp_path / ".mcp.json")],
    )

    assert result.exit_code != 0
    assert "ghost" in result.output


# ── ⑧ sync ───────────────────────────────────────────────────────────


def test_contract8_sync_refreshes_vendored_and_keeps_overlay(skill_file: Path) -> None:
    runner.invoke(app, ["catalog", "import", str(skill_file)])
    store = CatalogStore()
    from pouch.catalog.importer import apply_overlay

    apply_overlay(store, "aws-iam", Overlay(notes="prod-gate"))
    skill_file.write_text(
        _SKILL_MD.replace("IAM 절차", "IAM 절차 v2"), encoding="utf-8"
    )

    result = runner.invoke(app, ["catalog", "sync"])

    assert result.exit_code == 0
    entry = store.get("aws-iam")
    assert entry is not None
    assert entry.description == "IAM 절차 v2"  # upstream 재방문 반영
    assert entry.overlay is not None and entry.overlay.notes == "prod-gate"  # 개인화 생존
