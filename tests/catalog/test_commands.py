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

from pouch.catalog.commands import classify_source, find_plugin_roots
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


# ── ①-b 중첩 plugin 탐색 (marketplace 캐시 대응) ─────────────────────
#
# 실측(2026-07-02): ~/.claude/plugins/cache는 <marketplace>/<plugin>/<version>/
# 3단 구조라, end user가 최상위를 가리키면 classify가 실패했다.
# import가 중첩 루트를 스스로 찾아야 한다.


def _marketplace(tmp_path: Path, *plugins: str) -> Path:
    """<mkt>/<plugin>/<version>/{.mcp.json} 모양의 캐시 구조를 만든다."""
    mkt = tmp_path / "cache" / "some-marketplace"
    for name in plugins:
        root = mkt / name / "1.0.0"
        root.mkdir(parents=True)
        (root / ".mcp.json").write_text(
            json.dumps({"mcpServers": {f"{name}-mcp": {"command": "uvx", "args": ["x"]}}}),
            encoding="utf-8",
        )
    return mkt


def test_find_plugin_roots_discovers_nested_root(tmp_path: Path) -> None:
    mkt = _marketplace(tmp_path, "aws-core")

    roots = find_plugin_roots(mkt)

    assert roots == [mkt / "aws-core" / "1.0.0"]


def test_find_plugin_roots_skips_hidden_dirs(tmp_path: Path) -> None:
    mkt = _marketplace(tmp_path, "aws-core")
    # 번들 안의 숨김 사본(.claude/skills 등)은 루트로 세면 중복이 된다
    hidden = mkt / "aws-core" / "1.0.0" / ".claude" / "skills"
    hidden.mkdir(parents=True)

    roots = find_plugin_roots(mkt)

    assert roots == [mkt / "aws-core" / "1.0.0"]


def test_import_marketplace_dir_discovers_single_plugin(tmp_path: Path) -> None:
    mkt = _marketplace(tmp_path, "aws-core")

    result = runner.invoke(app, ["catalog", "import", str(mkt)])

    assert result.exit_code == 0
    assert CatalogStore().get("aws-core-mcp") is not None


def test_import_marketplace_dir_with_many_plugins_asks_to_pick(tmp_path: Path) -> None:
    mkt = _marketplace(tmp_path, "aws-core", "other-plugin")

    result = runner.invoke(app, ["catalog", "import", str(mkt)])

    assert result.exit_code != 0
    assert "aws-core" in result.output and "other-plugin" in result.output


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


def test_import_plugin_with_broken_skill_warns_and_continues(plugin_dir: Path) -> None:
    # 깨진 스킬 하나가 나머지를 인질로 잡으면 안 된다 — 경고와 함께 계속.
    broken = plugin_dir / "skills" / "broken-skill"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text("---\ndescription: d\n---\nB", encoding="utf-8")

    result = runner.invoke(app, ["catalog", "import", str(plugin_dir)])

    assert result.exit_code == 0  # 성한 조각은 담겼으니 성공
    assert "broken-skill" in result.output  # 뭘 건너뛰었는지 보인다
    store = CatalogStore()
    assert store.get("aws-iam") is not None
    assert store.get("broken-skill") is None


def test_import_single_skill_missing_name_fails_clearly(tmp_path: Path) -> None:
    # 단일 skill import는 건너뛸 나머지가 없다 — 대신 에러가 사람 말이어야 한다.
    path = tmp_path / "no-name" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\ndescription: d\n---\nB", encoding="utf-8")

    result = runner.invoke(app, ["catalog", "import", str(path)])

    assert result.exit_code != 0
    assert "name" in result.output
    assert "no-name" in result.output  # 어느 파일인지 알려준다 (✗ 'name' 금지)


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


def test_install_refuses_plugin_surfaced_entry(tmp_path: Path) -> None:
    # 표면을 플러그인이 관리하는 서버를 pouch가 또 등록하면 중복(거짓말)이다.
    from pouch.catalog.model import SURFACE_PLUGIN, ToolEntry, ToolKind

    CatalogStore().save(
        ToolEntry.linked(
            id="exa", kind=ToolKind.MCP, source="ecc", title="exa",
            description="d", recipe={"command": "npx"}, surface=SURFACE_PLUGIN,
        )
    )

    result = runner.invoke(
        app,
        ["catalog", "install", "exa", "--skills-dir", str(tmp_path / "s"),
         "--mcp-config", str(tmp_path / ".mcp.json")],
    )

    assert result.exit_code != 0
    assert "플러그인" in result.output
