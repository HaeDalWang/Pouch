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


def sets_dir() -> Path:
    """사용자 시작 세트 디렉토리(`~/.pouch/sets/`).

    내장 세트와 같은 형식의 JSON을 여기 두면 함께 읽힌다(같은 이름은 사용자 우선).
    나중에 세트 공유(raft)가 이 형식을 그대로 주고받는다.
    """
    return global_root() / "sets"


def usage_log_path() -> Path:
    """사용 이벤트 사이드카 로그(`~/.pouch/usage.jsonl`).

    카탈로그(레지스트리)와 분리된 append-only 라이프사이클 레이어.
    """
    return global_root() / "usage.jsonl"


def usage_summary_path() -> Path:
    """접힌 사용 요약(`~/.pouch/usage-summary.json`).

    오래된(경계 밖) 이벤트를 entry_id별 누적으로 접어 보존한다. 개별 시각은
    흐려지되 누적 횟수(습관 신호)는 남는다. `compacted_through` 마커로 집계가
    jsonl의 접힌 구간을 무시해 이중 계산을 막는다(멱등).
    """
    return global_root() / "usage-summary.json"


def state_path() -> Path:
    """활성 표면 상태 사이드카(`~/.pouch/state.json`).

    entry_id → installed_at·status. 카탈로그와 분리된 라이프사이클 기록.
    """
    return global_root() / "state.json"


def backup_dir() -> Path:
    """로컬 백업 목적지(`~/pouch-backups/`). `POUCH_BACKUP_DIR`로 오버라이드 가능.

    글로벌 루트(`~/.pouch`)의 *형제*라 백업 아카이브가 백업 대상 안에 들어가는
    재귀를 구조적으로 피한다. 복원 직전 자동 스냅샷도 여기에 함께 쌓인다.
    """
    override = os.environ.get("POUCH_BACKUP_DIR")
    return Path(override).expanduser() if override else Path.home() / "pouch-backups"


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


def claude_skills_dir() -> Path:
    """Claude Code 스킬 설치 위치(`~/.claude/skills/`).

    `CLAUDE_CONFIG_DIR` 환경변수로 오버라이드 가능(테스트/대체 설치 위치).
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "skills"


def project_mcp_config_path(start: Path | None = None) -> Path:
    """현재 프로젝트의 `.mcp.json` 경로. 프로젝트 루트를 못 찾으면 cwd 기준."""
    root = find_project_root(start) or (start or Path.cwd())
    return root / ".mcp.json"
