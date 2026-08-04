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
    usage_hook_command,
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


# ── 사용 기록의 출처(어느 표면에서 왔나) ─────────────────────────────
# 훅은 하네스마다 따로 걸리니, 명령에 자기 이름을 실어 보내면 로그가 출처를 갖는다.


def test_usage_hook_command_carries_host() -> None:
    assert usage_hook_command("claude") == "pouch evolve log --host claude"
    assert usage_hook_command("codex") == "pouch evolve log --host codex"


def test_usage_hook_command_without_host_stays_bare() -> None:
    """호스트를 모르면 옛 명령 그대로 — 없는 출처를 지어내지 않는다."""
    assert usage_hook_command(None) == POUCH_USAGE_HOOK_COMMAND


def test_usage_hook_install_with_host_writes_host_flag() -> None:
    installed = with_usage_hook_installed({}, host="codex")

    assert _post_groups(installed)[0]["hooks"][0]["command"] == usage_hook_command("codex")
    assert is_usage_hook_installed(installed)


def test_usage_hook_install_with_host_is_idempotent() -> None:
    once = with_usage_hook_installed({}, host="claude")
    twice = with_usage_hook_installed(once, host="claude")
    assert once == twice


def test_usage_hook_install_upgrades_old_bare_command() -> None:
    """이미 깔린 옛 훅은 갈아끼운다 — 나란히 두면 한 번 쓴 게 두 줄로 찍힌다."""
    old = with_usage_hook_installed({})  # 옛 형식(출처 없음)

    upgraded = with_usage_hook_installed(old, host="claude")

    commands = [h["command"] for g in _post_groups(upgraded) for h in g.get("hooks", [])]
    assert commands == [usage_hook_command("claude")]


def test_usage_hook_detect_finds_old_bare_command() -> None:
    """옛 형식도 '걸려 있음'으로 본다 — 중복 설치를 막는 판정이라."""
    assert is_usage_hook_installed(with_usage_hook_installed({}))


def test_usage_hook_remove_takes_hosted_command() -> None:
    installed = with_usage_hook_installed({}, host="codex")
    removed = with_usage_hook_removed(installed)

    assert not is_usage_hook_installed(removed)
    assert "hooks" not in removed


def test_usage_hook_remove_keeps_foreign_posttooluse_hooks() -> None:
    """남의 PostToolUse 훅은 안 건드린다 — 이름이 비슷해도 우리 것만 걷는다."""
    settings = with_usage_hook_installed({}, host="claude")
    settings["hooks"]["PostToolUse"].append(
        {"matcher": "Write", "hooks": [{"type": "command", "command": "make fmt"}]}
    )

    removed = with_usage_hook_removed(settings)

    commands = [h["command"] for g in _post_groups(removed) for h in g.get("hooks", [])]
    assert commands == ["make fmt"]


# ── 네이티브 메모리 스위치(A안 §1: pouch가 대체) ─────────────────────────


def test_native_memory_disable_sets_flag_false() -> None:
    from pouch.hooks.settings import is_native_memory_disabled, with_native_memory_disabled

    out = with_native_memory_disabled({})
    assert out["autoMemoryEnabled"] is False
    assert is_native_memory_disabled(out)


def test_native_memory_disable_is_idempotent_and_pure() -> None:
    from pouch.hooks.settings import with_native_memory_disabled

    base = {"autoMemoryEnabled": False, "other": 1}
    assert with_native_memory_disabled(base) is base  # 이미 꺼짐 → 그대로


def test_native_memory_disable_preserves_existing_and_input_unchanged() -> None:
    from pouch.hooks.settings import with_native_memory_disabled

    base = {"hooks": {"x": 1}}
    out = with_native_memory_disabled(base)
    assert out["hooks"] == {"x": 1}
    assert base == {"hooks": {"x": 1}}  # 입력 불변


def test_native_memory_enable_removes_flag() -> None:
    from pouch.hooks.settings import is_native_memory_disabled, with_native_memory_enabled

    out = with_native_memory_enabled({"autoMemoryEnabled": False, "k": 2})
    assert "autoMemoryEnabled" not in out
    assert out["k"] == 2
    assert not is_native_memory_disabled(out)
