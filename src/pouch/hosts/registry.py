"""호스트 어댑터 레지스트리 — 두 종류(훅·파일)를 이름으로 찾고 설치를 탐지한다.

훅 호스트(Claude·Codex)는 JSON 설정에 명령을 걸고, 파일 호스트(Kiro)는 홈에 기억
스냅샷을 쓴다. 하는 일이 달라 목록을 나눠 둔다 — 명령 계층이 종류별로 다르게 다룬다.
순서는 등록 순서를 따른다(출력·처리가 결정적).
"""

from __future__ import annotations

from pouch.hosts.base import FileHostAdapter, HostAdapter
from pouch.hosts.claude import ClaudeAdapter
from pouch.hosts.codex import CodexAdapter
from pouch.hosts.kiro import KiroSteeringAdapter

# 훅 호스트 — JSON 설정에 명령 훅(기억 주입 + 사용 로깅).
_HOOK_ADAPTERS: tuple[HostAdapter, ...] = (
    ClaudeAdapter(),
    CodexAdapter(),
)

# 파일 호스트 — 홈에 기억 스냅샷 파일(사용 로깅 없음, 기억 바뀌면 자동 갱신).
_FILE_ADAPTERS: tuple[FileHostAdapter, ...] = (KiroSteeringAdapter(),)


def hook_adapters() -> tuple[HostAdapter, ...]:
    """훅 호스트 어댑터 전체(등록 순서)."""
    return _HOOK_ADAPTERS


def file_adapters() -> tuple[FileHostAdapter, ...]:
    """파일 호스트 어댑터 전체(등록 순서)."""
    return _FILE_ADAPTERS


def all_names() -> list[str]:
    """등록된 모든 호스트 이름(훅+파일). `--host` 검증·안내용."""
    return [a.name for a in _HOOK_ADAPTERS] + [a.name for a in _FILE_ADAPTERS]


def get_hook_adapter(name: str) -> HostAdapter | None:
    """이름으로 훅 어댑터를 찾는다. 없으면 None."""
    for adapter in _HOOK_ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


def get_file_adapter(name: str) -> FileHostAdapter | None:
    """이름으로 파일 어댑터를 찾는다. 없으면 None."""
    for adapter in _FILE_ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


def detect_hook_installed() -> list[HostAdapter]:
    """설정 디렉토리가 존재하는 훅 호스트만(첫 연결도 잡히게 파일이 아닌 부모로 판단)."""
    return [a for a in _HOOK_ADAPTERS if a.config_path().parent.exists()]


def detect_file_supported() -> list[FileHostAdapter]:
    """이 머신에 설치된(전역 신호가 있는) 파일 호스트만."""
    return [a for a in _FILE_ADAPTERS if a.is_supported()]
