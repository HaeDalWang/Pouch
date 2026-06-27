"""settings.json 조작 순수 함수 검증."""

from __future__ import annotations

import json
from pathlib import Path

from pouch.hooks.settings import (
    POUCH_HOOK_COMMAND,
    is_installed,
    load_settings,
    with_hook_installed,
    with_hook_removed,
    write_settings,
)


def _commands(settings: dict) -> list[str]:
    return [
        hook["command"]
        for group in settings.get("hooks", {}).get("SessionStart", [])
        for hook in group.get("hooks", [])
    ]


def test_install_into_empty_settings() -> None:
    assert is_installed(with_hook_installed({}))


def test_install_is_idempotent() -> None:
    once = with_hook_installed({})
    twice = with_hook_installed(once)
    assert _commands(twice).count(POUCH_HOOK_COMMAND) == 1


def test_install_does_not_mutate_input() -> None:
    original: dict = {}
    with_hook_installed(original)
    assert original == {}


def test_install_preserves_existing_hooks() -> None:
    existing = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "other"}]}]}}
    result = with_hook_installed(existing)
    assert "other" in _commands(result)
    assert POUCH_HOOK_COMMAND in _commands(result)


def test_remove_cleans_up_empty_containers() -> None:
    installed = with_hook_installed({})
    removed = with_hook_removed(installed)
    assert not is_installed(removed)
    assert "hooks" not in removed


def test_remove_keeps_other_hooks() -> None:
    existing = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "other"}]}]}}
    installed = with_hook_installed(existing)
    removed = with_hook_removed(installed)
    assert _commands(removed) == ["other"]


def test_write_creates_backup_on_second_write(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "settings.json"

    # Act
    first_backup = write_settings(path, {"v": 1})
    second_backup = write_settings(path, {"v": 2})

    # Assert
    assert first_backup is None  # 첫 쓰기엔 백업 없음
    assert second_backup is not None
    assert json.loads(second_backup.read_text(encoding="utf-8"))["v"] == 1
    assert json.loads(path.read_text(encoding="utf-8"))["v"] == 2


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    assert load_settings(tmp_path / "nope.json") == {}
