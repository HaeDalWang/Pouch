"""Claude Code 어댑터 — 기존 settings.py 순수 함수를 그대로 감싼다.

배선 스키마의 원본은 settings.py다(`hooks.SessionStart[].hooks[{type,command}]` +
`PostToolUse` matcher). 이 어댑터는 그 함수들을 HostAdapter 계약에 맞춰 노출할 뿐,
로직을 복제하지 않는다 — 기존 Claude 테스트가 그대로 회귀 검증 역할을 한다.
"""

from __future__ import annotations

from pathlib import Path

from pouch import paths
from pouch.hooks.settings import (
    is_installed,
    is_usage_hook_installed,
    load_settings,
    with_hook_installed,
    with_hook_removed,
    with_usage_hook_installed,
    with_usage_hook_removed,
    write_settings,
)


class ClaudeAdapter:
    """Claude Code(`~/.claude/settings.json`) 배선."""

    name = "claude"
    display_name = "Claude Code"

    def config_path(self) -> Path:
        return paths.claude_settings_path()

    def load(self, path: Path) -> dict:
        return load_settings(path)

    def write(self, path: Path, config: dict) -> Path | None:
        return write_settings(path, config)

    def is_memory_installed(self, config: dict) -> bool:
        return is_installed(config)

    def with_memory_installed(self, config: dict) -> dict:
        return with_hook_installed(config)

    def with_memory_removed(self, config: dict) -> dict:
        return with_hook_removed(config)

    def is_usage_installed(self, config: dict) -> bool:
        return is_usage_hook_installed(config)

    def with_usage_installed(self, config: dict) -> dict:
        return with_usage_hook_installed(config)

    def with_usage_removed(self, config: dict) -> dict:
        return with_usage_hook_removed(config)

    def post_install_notes(self) -> list[str]:
        return []
