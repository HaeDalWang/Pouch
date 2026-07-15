"""`pouch hook --host` CLI 검증 — 대상 지정·전체 탐지·미지원 이름 처리.

세 호스트 경로를 임시로 격리해 실제 홈을 건드리지 않는다. --host를 주면 그 하나만,
안 주면 감지된 전체를 대상으로 삼는지, 모르는 이름은 종료하는지 확인한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.hooks.commands import app

runner = CliRunner()


@pytest.fixture
def hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Claude·Codex 디렉토리는 만들어 둔다(탐지 대상). Kiro는 워크스페이스라 별도.
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir()
    codex.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    monkeypatch.setenv("CODEX_HOME", str(codex))
    monkeypatch.chdir(tmp_path)  # .git 없음 → Kiro 미탐지
    return tmp_path


def _memory_installed(path: Path, key: str = "SessionStart") -> bool:
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    return bool(data)


def test_install_specific_host(hosts: Path) -> None:
    result = runner.invoke(app, ["install", "--host", "codex", "--yes"])
    assert result.exit_code == 0, result.stdout
    assert (hosts / "codex" / "hooks.json").exists()
    # Claude는 지정 안 했으니 안 건드림.
    assert not (hosts / "claude" / "settings.json").exists()


def test_install_unknown_host_exits(hosts: Path) -> None:
    result = runner.invoke(app, ["install", "--host", "nope", "--yes"])
    assert result.exit_code == 1
    assert "모르는 호스트" in result.stdout


def test_install_detected_all(hosts: Path) -> None:
    # --host 생략 → 감지된 전체(claude+codex)에 건다.
    result = runner.invoke(app, ["install", "--yes"])
    assert result.exit_code == 0, result.stdout
    assert (hosts / "claude" / "settings.json").exists()
    assert (hosts / "codex" / "hooks.json").exists()


def test_codex_shows_post_install_notes(hosts: Path) -> None:
    result = runner.invoke(app, ["install", "--host", "codex", "--yes"])
    assert "codex_hooks" in result.stdout  # experimental 플래그 안내
    # [features] TOML 섹션 헤더가 rich 마크업으로 먹히지 않고 그대로 보여야 한다
    # (사용자가 복붙할 값 — escape 안 하면 통째로 사라진다).
    assert "[features]" in result.stdout


def test_status_lists_all_hosts(hosts: Path) -> None:
    out = runner.invoke(app, ["status"]).stdout
    assert "Claude Code" in out
    assert "Codex" in out
    assert "Kiro" in out


def test_uninstall_specific_host(hosts: Path) -> None:
    runner.invoke(app, ["install", "--host", "codex", "--yes"])
    result = runner.invoke(app, ["uninstall", "--host", "codex"])
    assert result.exit_code == 0, result.stdout
    data = json.loads((hosts / "codex" / "hooks.json").read_text(encoding="utf-8"))
    assert not data.get("hooks")
