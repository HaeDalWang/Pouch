"""settings.json 조작 순수 함수 검증."""

from __future__ import annotations

import json
from pathlib import Path

from pouch.hooks.settings import (
    POUCH_HOOK_COMMAND,
    POUCH_USAGE_HOOK_COMMAND,
    is_installed,
    is_usage_hook_installed,
    load_settings,
    with_hook_installed,
    with_hook_removed,
    with_usage_hook_installed,
    with_usage_hook_removed,
    write_settings,
)


def _commands(settings: dict) -> list[str]:
    return [
        hook["command"]
        for group in settings.get("hooks", {}).get("SessionStart", [])
        for hook in group.get("hooks", [])
    ]


def _post_groups(settings: dict) -> list[dict]:
    return settings.get("hooks", {}).get("PostToolUse", [])


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


def test_usage_hook_install_and_detect() -> None:
    installed = with_usage_hook_installed({})
    assert is_usage_hook_installed(installed)
    # PostToolUse 그룹에 matcher와 명령이 실린다
    group = _post_groups(installed)[0]
    assert group["hooks"][0]["command"] == POUCH_USAGE_HOOK_COMMAND


def test_usage_hook_install_is_idempotent() -> None:
    once = with_usage_hook_installed({})
    twice = with_usage_hook_installed(once)
    assert once == twice


def test_usage_hook_does_not_mutate_input() -> None:
    original: dict = {}
    with_usage_hook_installed(original)
    assert original == {}


def test_usage_hook_coexists_with_session_start() -> None:
    # 두 hook이 한 설정에 공존한다 (SessionStart + PostToolUse)
    settings = with_usage_hook_installed(with_hook_installed({}))
    assert is_installed(settings)
    assert is_usage_hook_installed(settings)


def test_usage_hook_remove_cleans_up() -> None:
    installed = with_usage_hook_installed({})
    removed = with_usage_hook_removed(installed)
    assert not is_usage_hook_installed(removed)
    assert "hooks" not in removed


def test_usage_hook_remove_keeps_session_start() -> None:
    settings = with_usage_hook_installed(with_hook_installed({}))
    removed = with_usage_hook_removed(settings)
    assert not is_usage_hook_installed(removed)
    assert is_installed(removed)  # SessionStart는 남는다
