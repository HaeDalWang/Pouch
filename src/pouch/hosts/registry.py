"""호스트 어댑터 레지스트리 — 이름으로 찾고, 설치된 호스트를 탐지한다.

명령 계층은 여기만 본다. `--host`를 주면 그 어댑터 하나를, 안 주면 설정 파일이
실제로 있는 호스트 전체를 대상으로 삼는다(탐지). 순서는 등록 순서를 따른다
(claude → codex → kiro)로, 출력·처리 순서가 결정적이다.
"""

from __future__ import annotations

from pouch.hosts.base import HostAdapter
from pouch.hosts.claude import ClaudeAdapter
from pouch.hosts.codex import CodexAdapter
from pouch.hosts.kiro import KiroAdapter

# 등록 순서 = 출력·처리 순서(결정적). name → adapter.
_ADAPTERS: tuple[HostAdapter, ...] = (
    ClaudeAdapter(),
    CodexAdapter(),
    KiroAdapter(),
)


def all_adapters() -> tuple[HostAdapter, ...]:
    """등록된 모든 어댑터를 등록 순서로 반환한다."""
    return _ADAPTERS


def adapter_names() -> list[str]:
    """등록된 호스트 이름 목록(`--host` 검증·안내용)."""
    return [adapter.name for adapter in _ADAPTERS]


def get_adapter(name: str) -> HostAdapter | None:
    """이름으로 어댑터를 찾는다. 없으면 None."""
    for adapter in _ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


def detect_installed() -> list[HostAdapter]:
    """설정 디렉토리가 존재하는 호스트만 골라 반환한다(등록 순서).

    "이 머신에 이 에이전트가 있다"의 근사치 — 설정 파일이 아니라 그 *부모
    디렉토리* 유무로 판단한다. 훅 파일 자체는 아직 없어도(첫 연결) 그 에이전트를
    쓰고 있으면 디렉토리(`~/.claude`·`~/.codex`·프로젝트의 `.kiro/hooks`)는 있기
    때문이다. 파일 유무로 보면 첫 연결 대상이 안 잡히는 허점이 생긴다.

    Kiro는 워크스페이스 스코프라 프로젝트 안(.kiro/hooks/ 존재)에서만 잡힌다.
    """
    return [adapter for adapter in _ADAPTERS if adapter.config_path().parent.exists()]
