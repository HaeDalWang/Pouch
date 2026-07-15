"""Kiro 어댑터 — flat 배열 스키마(`{version, hooks:[{name,trigger,action}]}`).

Claude/Codex와 훅 JSON 모양이 달라 조작 함수를 새로 쓴다. 다만 명령 문자열과
matcher는 settings.py에서 가져와 단일 출처로 둔다(DRY — 주입/로깅 명령이 호스트마다
갈라지면 안 된다). 식별자는 `name` 필드(`pouch-memory`·`pouch-usage`)다.

Kiro 훅은 워크스페이스 스코프라 파일이 프로젝트 루트 밑(`.kiro/hooks/pouch.json`)에
산다. 전역 always-주입은 steering 파일(파일 씀 통로)의 몫이며 다음 판에서 다룬다.
"""

from __future__ import annotations

import copy
from pathlib import Path

from pouch import paths
from pouch.hooks.settings import (
    POUCH_HOOK_COMMAND,
    POUCH_USAGE_HOOK_COMMAND,
    POUCH_USAGE_HOOK_MATCHER,
    load_settings,
    write_settings,
)

_MEMORY_NAME = "pouch-memory"
_USAGE_NAME = "pouch-usage"
_VERSION = "v1"


def _has_hook(config: dict, name: str) -> bool:
    """해당 이름의 훅이 이미 등록돼 있는지."""
    return any(hook.get("name") == name for hook in config.get("hooks", []))


def _with_hook_added(config: dict, hook: dict) -> dict:
    """훅을 추가한 새 설정을 반환한다(이름으로 멱등). 기존 훅·version 보존."""
    if _has_hook(config, hook["name"]):
        return config
    updated = copy.deepcopy(config)
    updated.setdefault("version", _VERSION)
    updated.setdefault("hooks", []).append(hook)
    return updated


def _with_hook_removed(config: dict, name: str) -> dict:
    """해당 이름의 훅만 제거한 새 설정을 반환한다. 빈 컨테이너는 정리한다."""
    if not _has_hook(config, name):
        return config
    updated = copy.deepcopy(config)
    kept = [hook for hook in updated.get("hooks", []) if hook.get("name") != name]
    if kept:
        updated["hooks"] = kept
    else:
        updated.pop("hooks", None)
        updated.pop("version", None)
    return updated


def _memory_hook() -> dict:
    return {
        "name": _MEMORY_NAME,
        "trigger": "SessionStart",
        "action": {"type": "command", "command": POUCH_HOOK_COMMAND},
        "enabled": True,
    }


def _usage_hook() -> dict:
    return {
        "name": _USAGE_NAME,
        "trigger": "PostToolUse",
        "matcher": POUCH_USAGE_HOOK_MATCHER,
        "action": {"type": "command", "command": POUCH_USAGE_HOOK_COMMAND},
        "enabled": True,
    }


class KiroAdapter:
    """Kiro(`.kiro/hooks/pouch.json`, 워크스페이스) 배선."""

    name = "kiro"
    display_name = "Kiro"

    def config_path(self) -> Path:
        return paths.kiro_hooks_path()

    def load(self, path: Path) -> dict:
        return load_settings(path)

    def write(self, path: Path, config: dict) -> Path | None:
        return write_settings(path, config)

    def is_memory_installed(self, config: dict) -> bool:
        return _has_hook(config, _MEMORY_NAME)

    def with_memory_installed(self, config: dict) -> dict:
        return _with_hook_added(config, _memory_hook())

    def with_memory_removed(self, config: dict) -> dict:
        return _with_hook_removed(config, _MEMORY_NAME)

    def is_usage_installed(self, config: dict) -> bool:
        return _has_hook(config, _USAGE_NAME)

    def with_usage_installed(self, config: dict) -> dict:
        return _with_hook_added(config, _usage_hook())

    def with_usage_removed(self, config: dict) -> dict:
        return _with_hook_removed(config, _USAGE_NAME)

    def post_install_notes(self) -> list[str]:
        return [
            "Kiro 훅은 이 워크스페이스에서만 동작합니다(.kiro/hooks/pouch.json).",
            "다른 프로젝트에서도 쓰려면 그 프로젝트에서 다시 연결하세요.",
        ]
