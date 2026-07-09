"""세션 쪽지 조립 — 모든 조각이 만나는 자리(장부·렌더러·물러남·구역 분리).

정책([[pouch-proactive-nudge-policy]] 조각 4b): 쪽지를 SessionStart 통로에 실제로
실어보낸다. 두 함수로 나눈다:
  gather_nudge_summary : 계획을 읽어 종류별 개수만 낸다(부작용 없는 읽기 —
      SessionStart에서 compaction 같은 mutation은 하지 않는다).
  build_session_note   : 장부를 읽어 물러남을 판정하고, 심을 때만 텍스트를 내며
      장부에 record_shown 한다.

의존성 방향: 이 모듈은 evolution·catalog·memory의 *계산*만 임포트한다(commands는
안 건드림). memory.commands가 이 모듈을 임포트해 note_zone에 얹는다 — 단방향.

쪽지는 단일 집합 제안이다(proposal_id="cleanup") — 항목별이 아니라 "정리할 게
쌓였어요" 하나. 그래서 장부도 이 한 id의 last_shown·count만 추적한다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pouch.catalog.store import CatalogStore
from pouch.evolution.attach import AttachCandidate
from pouch.evolution.candidates import EvolveConfig, has_usage_signal
from pouch.evolution.ledger import last_shown, record_shown, shown_count
from pouch.evolution.nudge import NudgePolicy, NudgeSummary, plan_nudge
from pouch.evolution.orchestrate import plan_attach, plan_evolution
from pouch.memory.evolve import plan_memory_hygiene, plan_memory_pending
from pouch.memory.store import MemoryStore

# 쪽지는 하나의 집합 제안 — 장부에서 이 id 하나로 간격·물러남을 추적한다.
_NUDGE_ID = "cleanup"


def gather_nudge_summary(*, now: str) -> NudgeSummary:
    """지금 정리할 게 얼마나 쌓였는지 종류별 개수를 센다(읽기만, mutation 없음).

    evolve 명령과 같은 계획 함수를 쓰되 compaction은 하지 않는다(SessionStart에서
    로그를 재작성하지 않음). observe는 세지 않는다 — 행동이 없는 정보라 심을 게 없다.
    """
    store = CatalogStore()
    memory_store = MemoryStore()

    drops = [
        d
        for d in plan_evolution(now=now, config=EvolveConfig())
        if has_usage_signal(store.get(d.entry_id))
    ]
    attaches = plan_attach(now=now, store=store)
    reattaches = [c for c in attaches if c.kind == "reattach"]
    adopts = [c for c in attaches if c.kind == "adopt"]

    pending = plan_memory_pending(memory_store)
    hygiene = plan_memory_hygiene(memory_store, now=date.fromisoformat(now[:10]))

    return NudgeSummary(
        drop_count=len(drops),
        reattach_count=len(reattaches),
        adopt_count=len(adopts),
        memory_count=len(pending) + len(hygiene),
    )


def build_session_note(
    summary: NudgeSummary,
    *,
    now: str,
    ledger_path: Path | None = None,
    policy: NudgePolicy | None = None,
) -> str:
    """장부를 읽어 물러남을 판정하고, 심을 때만 텍스트를 내며 장부에 기록한다.

    안전: 심은 것만 장부에 기록한다(침묵은 장부 불변 — 유령 기록 방지). plan_nudge가
    문턱·간격·물러남을 모두 통과시켜 텍스트가 나올 때만 record_shown 한다.
    """
    policy = policy or NudgePolicy()
    note = plan_nudge(
        summary,
        last_shown=last_shown(_NUDGE_ID, ledger_path=ledger_path),
        shown_count=shown_count(_NUDGE_ID, ledger_path=ledger_path),
        now=now,
        policy=policy,
    )
    if not note:
        return ""  # 침묵 — 장부를 건드리지 않는다(유령 기록 없음)
    record_shown(_NUDGE_ID, now=now, ledger_path=ledger_path)
    return note
