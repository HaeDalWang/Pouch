"""핵심 도구 인식 — 실사용에서 "손에 맞은 도구"를 배운다(개인화 학습 레인 1).

핵심 = 많이 썼고(count) + 오래 걸쳐 썼다(span, 처음~마지막 사용 간격). span이
burst(한 주 몰아쓰고 끝)와 핵심(꾸준히 손이 감)을 가른다. **최근성은 안 본다** —
핵심은 잠깐의 공백(lull)에 흔들리지 않아야 하니까(기억 weight-면역과 같은 정신).

효과: 핵심 도구는 drop 제안에서 보호되고(오래 안 봐도 안 내림), 리포트에 인식된다.
순수 함수 — 시계도 IO도 없다(span은 이벤트 내부 시각만으로 난다).

한계(v0): 180일 밖 이벤트는 compaction으로 개별 시각이 흐려져(횟수만 보존) span에
안 잡힌다. 즉 핵심은 "보존된 상세 구간 안의 지속"을 본다 — 현재성 있는 핵심엔 충분하다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pouch.evolution.usage_log import UsageEvent

_DEFAULT_MIN_COUNT = 10
_DEFAULT_MIN_SPAN_DAYS = 21


@dataclass(frozen=True)
class CoreConfig:
    """핵심 판정 임계 — 매직넘버 회피."""

    min_count: int = _DEFAULT_MIN_COUNT  # 이만큼 넘게 썼고
    min_span_days: int = _DEFAULT_MIN_SPAN_DAYS  # 처음~마지막 간격이 이만큼 넘으면(지속) 핵심


def _span_days(first: str, last: str) -> float:
    """ISO8601 처음~마지막 사이 일수."""
    return (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds() / 86400


def core_entry_ids(
    events: list[UsageEvent],
    *,
    alias_map: dict[str, str] | None = None,
    config: CoreConfig = CoreConfig(),
) -> set[str]:
    """지속·빈도로 핵심 도구 entry_id를 뽑는다(순수).

    별칭(plugin_x_exa)은 정식 id로 접어 센다 — 안 그러면 같은 도구가 흩어져 count
    임계를 못 넘는다(집계·리포트와 같은 canonicalize 정신).
    """
    aliases = alias_map or {}
    agg: dict[str, list] = {}  # id -> [count, first_ts, last_ts]
    for event in events:
        eid = aliases.get(event.entry_id, event.entry_id)
        if eid in agg:
            agg[eid][0] += 1
            agg[eid][1] = min(agg[eid][1], event.ts)
            agg[eid][2] = max(agg[eid][2], event.ts)
        else:
            agg[eid] = [1, event.ts, event.ts]
    return {
        eid
        for eid, (count, first, last) in agg.items()
        if count >= config.min_count and _span_days(first, last) >= config.min_span_days
    }
