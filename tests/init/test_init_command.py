"""`pouch init` 비대화형 흐름 — 메모리 저장 + hook 연결 검증."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.cli import app
from pouch.memory.store import MemoryStore

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    # Claude 디렉토리는 만들어 둔다(탐지 대상). Codex는 없는 경로로 격리해
    # 이 개발 머신의 실제 ~/.codex 를 건드리지 않게 한다.
    claude = tmp_path / "claude"
    claude.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    return tmp_path


def test_init_saves_profile_memories(workspace: Path) -> None:
    # Act
    result = runner.invoke(
        app,
        ["init", "--role", "개발자", "--stack", "python", "--stack", "go",
         "--work-style", "테스트 먼저", "--yes"],
    )

    # Assert
    assert result.exit_code == 0, result.stdout
    names = {memory.name for memory in MemoryStore().list()}
    assert {"role", "environment", "stack", "work-style"} <= names


def test_init_links_hook(workspace: Path) -> None:
    # Act
    runner.invoke(app, ["init", "--role", "기획·PM", "--yes"])

    # Assert
    data = json.loads((workspace / "claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in data["hooks"]["SessionStart"]
        for hook in group["hooks"]
    ]
    assert "pouch memory context" in commands


def test_init_is_idempotent(workspace: Path) -> None:
    # Act — 두 번 실행
    runner.invoke(app, ["init", "--role", "개발자", "--yes"])
    runner.invoke(app, ["init", "--role", "개발자", "--yes"])

    # Assert — role 메모리는 하나 (덮어씀)
    roles = [m for m in MemoryStore().list() if m.name == "role"]
    assert len(roles) == 1


def _seed_native_feedback(project: Path) -> None:
    from pouch import paths

    native = paths.claude_project_memory_dir(project)
    native.mkdir(parents=True)
    (native / "feedback_stop.md").write_text(
        '---\nname: stop-here\ndescription: "d"\nmetadata:\n  type: feedback\n---\n본문\n',
        encoding="utf-8",
    )


def test_init_offers_adopt_migrates_but_keeps_native(workspace: Path) -> None:
    # 네이티브 메모리가 있으면 init(--yes)이 pouch로 옮긴다 — 단 네이티브는 안전망으로
    # 그대로 둔다(기본은 옮기기만, 다른 도구 설정을 기본으로 끄지 않음).
    from pouch import paths
    from pouch.hooks.settings import is_native_memory_disabled, load_settings

    _seed_native_feedback(workspace / "proj")

    result = runner.invoke(app, ["init", "--role", "개발자", "--yes"])
    assert result.exit_code == 0, result.stdout

    assert "stop-here" in {m.name for m in MemoryStore().list()}
    assert not is_native_memory_disabled(load_settings(paths.claude_settings_path()))


def test_init_without_native_memory_is_silent(workspace: Path) -> None:
    # 네이티브 메모리가 없으면 adopt 제안이 조용히 지나간다(init은 관문 아님).
    result = runner.invoke(app, ["init", "--role", "개발자", "--yes"])
    assert result.exit_code == 0, result.stdout
    assert "네이티브 메모리" not in result.stdout
