"""기억 evolve orchestration — 들어오는 문(pending)·나가는 문(hygiene) 조립.

카탈로그 evolve(pouch.evolution.orchestrate)와 같은 정신: 계산은 순수 함수
조합, 적용(promote/demote)은 store가 담당하고 CLI가 동의를 받은 뒤에만 부른다.
"""

from __future__ import annotations

from datetime import date

from pouch.memory.hygiene import HygieneCandidate, hygiene_candidates
from pouch.memory.liveness import check_reference_alive
from pouch.memory.model import MemoryEntry
from pouch.memory.pending import pending_entries
from pouch.memory.store import MemoryStore


def plan_memory_pending(store: MemoryStore) -> list[MemoryEntry]:
    """확인 대기 중인 pending 기억을 모은다(제안만, 아무것도 안 올림)."""
    return pending_entries(store.list())


def plan_memory_hygiene(store: MemoryStore, *, now: date) -> list[HygieneCandidate]:
    """인덱스에서 강등할 후보를 계산한다(제안만, 아무것도 안 내림).

    URL reference는 네트워크 호출 없이 "판단 불가=생존"으로 본다(v0 스코프) —
    로컬 경로만 실제로 존재 여부를 확인한다.
    """
    return hygiene_candidates(list(store.list()), now=now, is_alive=check_reference_alive)
