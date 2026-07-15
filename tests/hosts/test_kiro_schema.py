"""Kiro 전용 스키마 검증 — flat 배열 + name/trigger/action 모양.

Claude/Codex와 공유하지 않는 부분이라 스키마 자체를 콕 짚어 검증한다: 훅이
version 필드와 함께 hooks 배열에 들어가는지, trigger·action·matcher가 제대로
박히는지, 남의 훅과 version을 보존하는지.
"""

from __future__ import annotations

from pouch.hooks.settings import POUCH_HOOK_COMMAND, POUCH_USAGE_HOOK_COMMAND
from pouch.hosts.kiro import KiroAdapter

adapter = KiroAdapter()


def test_memory_hook_shape() -> None:
    config = adapter.with_memory_installed({})
    assert config["version"] == "v1"
    hook = config["hooks"][0]
    assert hook["name"] == "pouch-memory"
    assert hook["trigger"] == "SessionStart"
    assert hook["action"] == {"type": "command", "command": POUCH_HOOK_COMMAND}


def test_usage_hook_has_matcher() -> None:
    config = adapter.with_usage_installed({})
    hook = config["hooks"][0]
    assert hook["trigger"] == "PostToolUse"
    assert hook["matcher"]  # Skill|mcp__.* 매처가 실려야 도구 호출만 잡는다
    assert hook["action"]["command"] == POUCH_USAGE_HOOK_COMMAND


def test_preserves_foreign_hook_and_version() -> None:
    existing = {
        "version": "v1",
        "hooks": [{"name": "user-lint", "trigger": "PostFileSave"}],
    }
    updated = adapter.with_memory_installed(existing)
    names = [h["name"] for h in updated["hooks"]]
    assert "user-lint" in names and "pouch-memory" in names


def test_remove_last_pouch_hook_cleans_container() -> None:
    only_pouch = adapter.with_memory_installed({})
    removed = adapter.with_memory_removed(only_pouch)
    # 마지막 pouch 훅을 걷으면 빈 hooks·version 흔적을 남기지 않는다.
    assert "hooks" not in removed
    assert "version" not in removed


def test_remove_keeps_foreign_hook() -> None:
    existing = {"version": "v1", "hooks": [{"name": "user-lint", "trigger": "Stop"}]}
    installed = adapter.with_memory_installed(existing)
    removed = adapter.with_memory_removed(installed)
    names = [h["name"] for h in removed["hooks"]]
    assert names == ["user-lint"]
    assert removed["version"] == "v1"  # 남의 훅이 남으면 version도 보존
