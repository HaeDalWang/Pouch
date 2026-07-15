"""HostAdapter 계약 — 각 에이전트에 훅을 거는 "배선"의 공통 인터페이스.

배선의 모든 조작 함수는 입력 config dict를 변경하지 않고 새 dict를 반환한다
(immutability). 멱등(다시 걸어도 결과 같음)이고 기존 배선을 보존한다 — pouch 자체
훅과 같은 안전장치다. 두 기능을 건다: 기억 주입(세션 시작)과 사용 로깅(도구 호출).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class HostAdapter(Protocol):
    """한 에이전트(호스트)에 pouch를 연결하는 어댑터.

    config_path가 가리키는 JSON 파일을 load→조작→write 하는 흐름이 공통이다.
    조작 함수는 순수(입력 불변·새 dict 반환)해서 파일 IO 없이 단위 테스트할 수 있다.
    """

    name: str
    display_name: str

    def config_path(self) -> Path:
        """이 호스트의 훅 설정 파일 경로."""
        ...

    def load(self, path: Path) -> dict:
        """설정 파일을 읽는다. 없거나 비어있으면 빈 dict."""
        ...

    def write(self, path: Path, config: dict) -> Path | None:
        """설정을 기록한다. 기존 파일이 있었으면 백업하고 그 경로를 반환한다."""
        ...

    def is_memory_installed(self, config: dict) -> bool:
        """기억 주입(세션 시작) 배선이 이미 걸려 있는지."""
        ...

    def with_memory_installed(self, config: dict) -> dict:
        """기억 주입 배선을 더한 새 설정(멱등·기존 보존)."""
        ...

    def with_memory_removed(self, config: dict) -> dict:
        """기억 주입 배선만 걷어낸 새 설정. 빈 컨테이너는 정리한다."""
        ...

    def is_usage_installed(self, config: dict) -> bool:
        """사용 로깅(도구 호출) 배선이 이미 걸려 있는지."""
        ...

    def with_usage_installed(self, config: dict) -> dict:
        """사용 로깅 배선을 더한 새 설정(멱등·기존 보존)."""
        ...

    def with_usage_removed(self, config: dict) -> dict:
        """사용 로깅 배선만 걷어낸 새 설정. 빈 컨테이너는 정리한다."""
        ...

    def post_install_notes(self) -> list[str]:
        """설치 직후 사용자에게 보여줄 추가 안내(없으면 빈 리스트).

        Codex처럼 훅을 걸어도 experimental 플래그·신뢰 등록이 더 필요한 호스트가
        여기에 안내 문구를 담는다. 기본은 빈 리스트(추가 조치 불필요).
        """
        ...
