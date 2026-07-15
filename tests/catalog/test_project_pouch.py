"""프로젝트별 주머니 — 프로젝트 스코프 카탈로그(경로·import --project·list)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch import paths
from pouch.catalog.commands import app
from pouch.catalog.store import CatalogStore

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    return project


def _skill_dir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} 스킬\n---\n본문\n", encoding="utf-8"
    )
    return d


def test_project_catalog_dir_in_and_out(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert paths.project_catalog_dir() == workspace / ".pouch" / "catalog"
    outside = workspace.parent / "nowhere"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert paths.project_catalog_dir() is None


def test_import_project_registers_to_project_catalog(workspace: Path, tmp_path: Path) -> None:
    skill = _skill_dir(tmp_path / "src", "clientsec")

    result = runner.invoke(app, ["import", str(skill / "SKILL.md"), "--project"])
    assert result.exit_code == 0, result.stdout
    assert "이 프로젝트 주머니에 담았습니다" in result.stdout

    # 프로젝트 카탈로그엔 들어가고, 전역 소스 스테이징엔 안 들어간다.
    proj = {e.id for e in CatalogStore(catalog_dir=workspace / ".pouch" / "catalog").list()}
    assert "clientsec" in proj
    assert list(CatalogStore(catalog_dir=paths.sources_dir()).list()) == []


def test_import_project_outside_project_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    outside = tmp_path / "nowhere"
    outside.mkdir()
    monkeypatch.chdir(outside)
    skill = _skill_dir(tmp_path / "src", "x")

    result = runner.invoke(app, ["import", str(skill / "SKILL.md"), "--project"])
    assert result.exit_code != 0
    assert "프로젝트 안에서만" in result.stdout


def test_list_shows_project_section(workspace: Path, tmp_path: Path) -> None:
    skill = _skill_dir(tmp_path / "src", "clientsec")
    runner.invoke(app, ["import", str(skill / "SKILL.md"), "--project"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.stdout
    assert "이 프로젝트 주머니" in result.stdout
    assert "clientsec" in result.stdout
