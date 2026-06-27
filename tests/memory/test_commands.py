"""`pouch memory` CLI 통합 검증 — 임시 글로벌/프로젝트 경로로 격리."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.memory.commands import app

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """글로벌은 POUCH_HOME으로, 프로젝트는 .git 있는 cwd로 격리한다."""
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    return tmp_path


def test_add_global_then_list(workspace: Path) -> None:
    # Arrange / Act
    result = runner.invoke(
        app,
        ["add", "-n", "prefers-uv", "-d", "파이썬은 uv", "-b", "pip 대신 uv", "-t", "user", "-s", "global"],
    )

    # Assert
    assert result.exit_code == 0, result.stdout
    listed = runner.invoke(app, ["list"])
    assert "prefers-uv" in listed.stdout


def test_add_refreshes_index(workspace: Path) -> None:
    # Act
    runner.invoke(app, ["add", "-n", "x", "-d", "d", "-b", "b", "-s", "global"])

    # Assert
    index = workspace / "global" / "memory" / "MEMORY.md"
    assert index.exists()
    assert "x" in index.read_text(encoding="utf-8")


def test_add_project_scope_writes_under_repo(workspace: Path) -> None:
    # Act
    result = runner.invoke(app, ["add", "-n", "p", "-d", "d", "-b", "b", "-s", "project"])

    # Assert
    assert result.exit_code == 0, result.stdout
    assert (workspace / "proj" / ".pouch" / "memory" / "p.md").exists()


def test_recall_finds_match(workspace: Path) -> None:
    # Arrange
    runner.invoke(app, ["add", "-n", "x", "-d", "파이썬 메모", "-b", "uv 사용", "-s", "global"])

    # Act
    result = runner.invoke(app, ["recall", "파이썬"])

    # Assert
    assert "x" in result.stdout


def test_forget_removes_memory(workspace: Path) -> None:
    # Arrange
    runner.invoke(app, ["add", "-n", "x", "-d", "d", "-b", "b", "-s", "global"])

    # Act
    result = runner.invoke(app, ["forget", "x"])

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "x" not in runner.invoke(app, ["list"]).stdout


def test_forget_missing_exits_nonzero(workspace: Path) -> None:
    result = runner.invoke(app, ["forget", "ghost"])
    assert result.exit_code == 1
