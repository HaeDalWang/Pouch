"""들어오는 문 — 저마찰 유입과 타입별 마찰.

긴장: 저마찰로 마구 담으면 인덱스가 범람하고, 신중히 담으면 저마찰이 아니다.
해법 = 스테이징 계층. project·reference는 pending으로 바로 얹혀도(저마찰) 위생이
나중에 자가 청소하니 안전하다 — 마찰이 "담을 때"에서 "리뷰 때 일괄"로 이동한다.

feedback·boundary·user는 pending 우회를 코드로 막는다(확인 필수). 오독한
일회성 지적이 매 세션 주입되는 standing rule로 굳는 위험이 boundary deny
오독과 동형이라, 사람이 보는 자리에서만 인덱스에 오른다.
"""

from __future__ import annotations

from collections.abc import Iterable

from pouch.memory.model import MemoryEntry, MemoryState, MemoryType

LOW_FRICTION_TYPES = frozenset({MemoryType.PROJECT, MemoryType.REFERENCE})


def is_low_friction(mem_type: MemoryType) -> bool:
    """pending 스테이징을 확인 없이 허용할 타입인가."""
    return mem_type in LOW_FRICTION_TYPES


def pending_entries(entries: Iterable[MemoryEntry]) -> list[MemoryEntry]:
    """확인 대기 중인(PENDING) 기억만 골라낸다."""
    return [entry for entry in entries if entry.state is MemoryState.PENDING]
