"""`pouch hook` CLI 검증 — 임시 CLAUDE_CONFIG_DIR로 격리."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.hooks.commands import app

runner = CliRunner()


@pytest.fixture
def claude_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    return tmp_path


def _commands(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        hook["command"]
        for group in data.get("hooks", {}).get("SessionStart", [])
        for hook in group.get("hooks", [])
    ]


def test_install_yes_writes_hook(claude_dir: Path) -> None:
    # Act
    result = runner.invoke(app, ["install", "--yes"])

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "pouch memory context" in _commands(claude_dir / "settings.json")


def test_install_twice_is_idempotent(claude_dir: Path) -> None:
    runner.invoke(app, ["install", "--yes"])
    result = runner.invoke(app, ["install", "--yes"])
    assert "이미" in result.stdout


def test_uninstall_removes_hook(claude_dir: Path) -> None:
    # Arrange
    runner.invoke(app, ["install", "--yes"])

    # Act
    result = runner.invoke(app, ["uninstall"])

    # Assert
    assert result.exit_code == 0, result.stdout
    data = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert not data.get("hooks")


def test_status_reflects_state(claude_dir: Path) -> None:
    assert "안 됨" in runner.invoke(app, ["status"]).stdout
    runner.invoke(app, ["install", "--yes"])
    assert "연결됨" in runner.invoke(app, ["status"]).stdout


def test_install_declined_writes_nothing(claude_dir: Path) -> None:
    # Act — 확인 프롬프트에 'n' 입력
    result = runner.invoke(app, ["install"], input="n\n")

    # Assert
    assert "취소" in result.stdout
    assert not (claude_dir / "settings.json").exists()
