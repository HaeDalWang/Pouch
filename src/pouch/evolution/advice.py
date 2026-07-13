"""조언 분류 — plugin 관측 사용을 진화 조언으로. 순수 함수. (A→B 전환 조각 1)

정책([[pouch-evolution-management-layer]]): 진화 = 행위(drop/reattach)가 아니라
조언. surface:plugin(관측 전용)은 손댈 수 없는 대상이 아니라 조언 신호다. pouch는
표면을 강제로 안 바꾸고, 소유자(ECC/사용자)에게 사람 말로 조언만 한다.

핵심 절제(추측 잔소리 회피): plugin 도구를 "안 씀"으로 판정하는 건 관측 증거가
있을 때만. 한 번도 본 적 없는 plugin 도구는 침묵한다 — "본 적 없으니 꺼"는 추측이라
계속 피한 잔소리 함정. 관측한 것만 조언한다.

non-plugin(pouch 소유)은 여기서 안 다룬다 — drop/reattach 경로가 소유. (B)는 (A)의
상위집합: pouch가 진짜 소유한 표면엔 행위가 여전히 유효하고, 전엔 비어 있던 plugin
쪽(관측만 가능한 표면)을 이 조언 경로가 새로 채운다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pouch.catalog.model import SURFACE_PLUGIN, ToolEntry
from pouch.evolution.aggregate import UsageStat

_KIND_REINFORCE = "reinforce"
_KIND_SUGGEST_OFF = "suggest_off"
_KIND_ORDER = {_KIND_REINFORCE: 0, _KIND_SUGGEST_OFF: 1}


@dataclass(frozen=True)
class Advice:
    """한 plugin 도구에 대한 진화 조언(행위 아님 — 소유자에게 전할 말).

    reinforce: 최근 잘 씀(강화 신호). suggest_off: 예전엔 썼는데 지금 stale
    ("ECC에서 꺼볼까요" 안내). pouch는 이걸 실행하지 않는다 — 조언만.
    """

    target: str  # 대상 entry_id
    kind: str  # "reinforce" | "suggest_off"
    count: int
    last_used: str


def _days_between(earlier: str, later: str) -> float:
    """ISO8601 두 시각 사이 일수. earlier가 미래면 음수."""
    delta = datetime.fromisoformat(later) - datetime.fromisoformat(earlier)
    return delta.total_seconds() / 86400


def plan_advice(
    entries: list[ToolEntry],
    stats: dict[str, UsageStat],
    *,
    now: str,
    stale_days: int,
) -> list[Advice]:
    """plugin 도구의 관측 사용을 조언으로 분류한다(순수 — now 주입).

    관측 증거(stats)가 있는 plugin 도구만 본다. 최근 사용이 stale 임계를 넘었으면
    suggest_off, 아니면 reinforce. 한 번도 안 본 것·non-plugin은 조언 없음(침묵).
    """
    advices: list[Advice] = []
    for entry in entries:
        if entry.surface != SURFACE_PLUGIN:
            continue  # pouch 소유는 drop/reattach 경로가 소유
        stat = stats.get(entry.id)
        if stat is None:
            continue  # 관측 증거 없음 → 추측 안 함(침묵)
        kind = (
            _KIND_SUGGEST_OFF
            if _days_between(stat.last_used, now) >= stale_days
            else _KIND_REINFORCE
        )
        advices.append(
            Advice(target=entry.id, kind=kind, count=stat.count, last_used=stat.last_used)
        )
    return sorted(advices, key=lambda a: (_KIND_ORDER[a.kind], a.target))
