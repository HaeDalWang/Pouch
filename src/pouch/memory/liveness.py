"""reference 생존성 판정 — upstream 증발(rehome)의 기억판.

reference 메모리는 대개 "무언가를 가리키는" 한 줄이다(대시보드 URL, 로컬 경로).
그 가리키는 자원이 죽었으면 기억 자체가 죽은 것 — 나이가 아니라 이게 진짜 신호다.

자원을 못 찾으면(자연어 설명뿐인 reference) 살아있다고 본다 — 판단 불가를
죽음으로 오판하면 위생이 멀쩡한 기억을 강등 후보로 잘못 올린다.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from pouch.memory.model import MemoryEntry

_URL_PATTERN = re.compile(r"https?://\S+")
_PATH_PATTERN = re.compile(r"(?:~|/)[\w./\-]+")


def extract_resource(body: str) -> str | None:
    """body에서 첫 URL 또는 로컬 경로를 뽑는다. 없으면 None."""
    url_match = _URL_PATTERN.search(body)
    if url_match:
        return url_match.group(0)
    path_match = _PATH_PATTERN.search(body)
    if path_match:
        return path_match.group(0)
    return None


def check_reference_alive(
    entry: MemoryEntry, *, http_head: Callable[[str], bool] | None = None
) -> bool:
    """entry.body가 가리키는 자원이 살아있는지 판정한다.

    URL은 http_head 예측자로(기본은 실제 네트워크 HEAD는 호출부 책임 —
    주입 없이 부르면 판단 불가로 취급해 오탐을 피한다), 로컬 경로는
    파일시스템 존재로, 못 찾으면 살아있다고 본다.
    """
    resource = extract_resource(entry.body)
    if resource is None:
        return True
    if resource.startswith(("http://", "https://")):
        return http_head(resource) if http_head else True
    return Path(resource).expanduser().exists()
