"""usage 집계 — 이벤트 스트림을 entry_id별 통계로 접는다. 순수 함수.

신호 정책: 최근성 주축(last_used) + 횟수 보조(count).
ISO8601 문자열은 사전식 비교가 곧 시간순이라 last_used = max(ts)로 충분하다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from pouch.evolution.usage_log import UsageEvent


@dataclass(frozen=True)
class UsageStat:
    """한 entry_id의 집계. count=사용 횟수, last_used=최신 ts(ISO8601)."""

    count: int
    last_used: str


def events_within(
    events: list[UsageEvent], *, now: str, window_days: int
) -> list[UsageEvent]:
    """now 기준 window_days 안의 이벤트만 남긴다(순수 — now 주입)."""
    cutoff = datetime.fromisoformat(now) - timedelta(days=window_days)
    return [e for e in events if datetime.fromisoformat(e.ts) >= cutoff]


def aggregate_usage(events: list[UsageEvent]) -> dict[str, UsageStat]:
    """이벤트를 entry_id별로 접는다. count 누적, last_used는 최신 ts."""
    stats: dict[str, UsageStat] = {}
    for event in events:
        prev = stats.get(event.entry_id)
        if prev is None:
            stats[event.entry_id] = UsageStat(count=1, last_used=event.ts)
        else:
            stats[event.entry_id] = UsageStat(
                count=prev.count + 1,
                last_used=max(prev.last_used, event.ts),
            )
    return stats
