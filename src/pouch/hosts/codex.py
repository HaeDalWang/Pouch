"""Codex 어댑터 — Claude와 훅 JSON 스키마가 글자까지 같다.

그래서 settings.py의 순수 함수를 그대로 재사용한다(조작 로직 복제 없음). Claude와
다른 건 딱 둘: 설정 파일 경로(`~/.codex/hooks.json`)와, 훅을 걸어도 추가 조치가
필요하다는 점 — Codex는 훅이 experimental 플래그 뒤에 있고, 명령 훅은 해시 기반
신뢰 등록을 거쳐야 실제로 발화한다. 그 두 조치를 post_install_notes로 안내한다.
"""

from __future__ import annotations

from pathlib import Path

from pouch import paths
from pouch.hosts.base import LAYOUT_FILE, LAYOUT_SKILLS_ROOT, Toolbox
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


class CodexAdapter:
    """Codex(`~/.codex/hooks.json`) 배선. Claude와 스키마 공유."""

    name = "codex"
    display_name = "Codex"

    def config_path(self) -> Path:
        return paths.codex_hooks_path()

    def toolbox_paths(self) -> tuple[Toolbox, ...]:
        """Codex가 도구를 두는 자리 — 스킬 폴더·훅 파일(실측 2026-07-21).

        `~/.codex/agents/*.toml`도 있지만 pouch가 아는 형식이 아니라 안 훑는다
        (지어내지 않는다 — 읽을 줄 알게 되면 그때 칸을 늘린다).
        """
        return (
            Toolbox(path=paths.codex_skills_dir(), layout=LAYOUT_SKILLS_ROOT),
            Toolbox(path=paths.codex_hooks_path(), layout=LAYOUT_FILE),
        )

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
        return [
            "Codex는 훅이 아직 experimental이라 한 번 켜줘야 합니다:",
            "  ~/.codex/config.toml 에 [features] codex_hooks = true 추가",
            "그리고 Codex에서 /hooks 를 열어 이 훅을 신뢰(trust)해야 실제로 발화합니다",
            "  (훅 정의가 바뀌면 다시 신뢰가 필요합니다 — 해시 기반).",
        ]
