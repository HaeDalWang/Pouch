"""파일 호스트 스냅샷 갱신 — 기억이 바뀌면 링크된 파일을 다시 쓴다.

파일 호스트(Kiro steering 등)는 "한 번 찍는 사진"이라 기억이 바뀌면 낡는다. 이
모듈이 그 낡음을 자동으로 해소한다: MemoryStore.save/forget가 MEMORY.md를 재생성할
때 이 refresh_linked를 나란히 호출한다(store 안에서 함수-지역 import로 순환 회피).

두 원칙:
- **전역 기억만.** steering 파일은 모든 워크스페이스에서 읽히므로 프로젝트 기억을
  담으면 다른 프로젝트로 샌다. GLOBAL 스코프만 렌더한다.
- **링크된 것만.** 스냅샷 파일이 이미 있는(=사용자가 연결한) 호스트만 다시 쓴다.
  연결 안 한 호스트에 파일을 새로 만들지 않는다(파일 존재가 곧 opt-in 게이트).
"""

from __future__ import annotations

from collections.abc import Iterable

from pouch.memory.model import MemoryEntry, MemoryScope


def render_file_body(entries: Iterable[MemoryEntry]) -> str:
    """파일 호스트에 담을 본문 — 전역 기억만, 세션-휘발 구역 없음.

    훅 통로의 render_session_context와 달리 정렬 체크포인트·먼저 내미는 제안 쪽지를
    싣지 않는다(스냅샷에 담으면 낡는다). 파일 = "안정적으로 기억하는 것"뿐.
    """
    from pouch.memory.context import render_context

    global_only = [e for e in entries if e.scope is MemoryScope.GLOBAL]
    return render_context(global_only)


def refresh_linked(entries: Iterable[MemoryEntry]) -> list[str]:
    """링크된(파일이 이미 있는) 파일 호스트의 스냅샷을 다시 쓴다.

    다시 쓴 호스트 이름 목록을 반환한다(호출부 로깅/테스트용). 링크된 게 없으면
    빈 리스트 — 아무 파일도 새로 만들지 않는다.
    """
    from pouch.hosts.registry import file_adapters

    materialized = list(entries)
    body = render_file_body(materialized)
    refreshed: list[str] = []
    for adapter in file_adapters():
        if adapter.is_linked():
            adapter.link(body)
            refreshed.append(adapter.name)
    return refreshed
