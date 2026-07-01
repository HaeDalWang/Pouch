"""pouch 저장소 경로 결정.

글로벌은 홈 아래 고정, 프로젝트는 작업 위치에서 위로 올라가며 탐지한다.
모든 메모리는 플랫 마크다운 파일이라 이 디렉토리를 그대로 백업(S3 sync 등)할 수 있다.
"""

from __future__ import annotations

import os
from pathlib import Path


def global_root() -> Path:
    """pouch 전역 루트. `POUCH_HOME` 환경변수로 오버라이드 가능(테스트/이전 용이)."""
    override = os.environ.get("POUCH_HOME")
    return Path(override).expanduser() if override else Path.home() / ".pouch"


def global_memory_dir() -> Path:
    """사용자 전역 메모리 디렉토리(`~/.pouch/memory/`)."""
    return global_root() / "memory"


def catalog_dir() -> Path:
    """도구 카탈로그 디렉토리(`~/.pouch/catalog/`)."""
    return global_root() / "catalog"


def usage_log_path() -> Path:
    """사용 이벤트 사이드카 로그(`~/.pouch/usage.jsonl`).

    카탈로그(레지스트리)와 분리된 append-only 라이프사이클 레이어.
    """
    return global_root() / "usage.jsonl"


def find_project_root(start: Path | None = None) -> Path | None:
    """`.pouch/` 또는 `.git`이 있는 가장 가까운 상위 디렉토리를 찾는다."""
    start = (start or Path.cwd()).resolve()
    for directory in (start, *start.parents):
        if (directory / ".pouch").is_dir() or (directory / ".git").exists():
            return directory
    return None


def project_memory_dir(start: Path | None = None) -> Path | None:
    """현재 프로젝트의 메모리 디렉토리. 프로젝트 루트를 못 찾으면 None."""
    root = find_project_root(start)
    return (root / ".pouch" / "memory") if root else None


def claude_settings_path() -> Path:
    """Claude Code 사용자 설정 파일 경로(`~/.claude/settings.json`).

    `CLAUDE_CONFIG_DIR` 환경변수로 오버라이드 가능(테스트/대체 설치 위치).
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "settings.json"
