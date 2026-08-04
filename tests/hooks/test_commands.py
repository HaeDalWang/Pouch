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
    # Claude 디렉토리는 존재(탐지 대상), Codex는 없는 경로로 격리(실제 ~/.codex 오염 방지).
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    # cwd를 .git 없는 임시 위치로 옮겨 Kiro 워크스페이스 탐지도 격리한다.
    monkeypatch.chdir(tmp_path)
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
    # 로깅 명령엔 하네스 이름이 실린다 — 그래야 기록이 "어디서 난 사용"인지 안다.
    runner.invoke(app, ["install", "--yes"])

    settings = claude_dir / "settings.json"
    assert "pouch memory context" in _commands(settings)
    assert "pouch evolve log --host claude" in _post_commands(settings)


def test_install_upgrades_already_linked_old_hook(claude_dir: Path) -> None:
    """이미 연결된 사람도 갈아끼워져야 한다.

    옛 훅(출처 없음)도 '걸려 있음'으로 세다 보니, "이미 연결됨"으로 건너뛰면
    옛 사용자는 영원히 출처 없는 기록만 쌓는다. 판정은 '걸려 있나'가 아니라
    '바꿀 게 있나'여야 한다.
    """
    settings = claude_dir / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "pouch memory context"}]}
                    ],
                    "PostToolUse": [
                        {
                            "matcher": "Skill|mcp__.*",
                            "hooks": [{"type": "command", "command": "pouch evolve log"}],
                        },
                        {
                            "matcher": "Write",
                            "hooks": [{"type": "command", "command": "make fmt"}],
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    runner.invoke(app, ["install", "--yes"])

    post = _post_commands(settings)
    assert "pouch evolve log --host claude" in post
    assert "pouch evolve log" not in post  # 옛 명령은 남지 않는다(중복 기록 방지)
    assert "make fmt" in post  # 남의 훅은 그대로


def test_install_twice_is_still_quiet(claude_dir: Path) -> None:
    """바뀔 게 없으면 두 번째 install은 아무것도 안 쓴다(멱등)."""
    runner.invoke(app, ["install", "--yes"])
    settings = claude_dir / "settings.json"
    before = settings.read_text(encoding="utf-8")

    result = runner.invoke(app, ["install", "--yes"])

    assert settings.read_text(encoding="utf-8") == before
    assert "이미 연결" in result.stdout


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
