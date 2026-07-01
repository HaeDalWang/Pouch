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


def _post_commands(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        hook["command"]
        for group in data.get("hooks", {}).get("PostToolUse", [])
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


def test_install_registers_both_hooks(claude_dir: Path) -> None:
    # install은 SessionStart(기억 주입)와 PostToolUse(사용 로깅) 둘 다 건다.
    # 사용 로깅 hook이 걸려야 usage.jsonl이 쌓이고 evolve가 눈을 뜬다.
    runner.invoke(app, ["install", "--yes"])

    settings = claude_dir / "settings.json"
    assert "pouch memory context" in _commands(settings)
    assert "pouch evolve log" in _post_commands(settings)


def test_uninstall_removes_both_hooks(claude_dir: Path) -> None:
    runner.invoke(app, ["install", "--yes"])

    result = runner.invoke(app, ["uninstall"])

    assert result.exit_code == 0, result.stdout
    data = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert not data.get("hooks")  # 두 hook 다 정리됨


def test_status_reflects_both_hooks(claude_dir: Path) -> None:
    runner.invoke(app, ["install", "--yes"])
    out = runner.invoke(app, ["status"]).stdout
    assert "기억" in out and "사용" in out  # 두 연결 상태를 각각 보여준다
