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
        stats[event.entry_id] = _merge(stats.get(event.entry_id), 1, event.ts)
    return stats


def canonicalize_stats(
    stats: dict[str, UsageStat], mapping: dict[str, str]
) -> dict[str, UsageStat]:
    """usage entry_id를 카탈로그 정식 id로 접는다(순수).

    같은 도구가 두 이름(런타임 별칭 vs 카탈로그 id)으로 찍혀도 하나로 합산 —
    count는 합, last_used는 최신. 매핑에 없는 id는 그대로 통과한다.
    """
    merged: dict[str, UsageStat] = {}
    for entry_id, stat in stats.items():
        canonical = mapping.get(entry_id, entry_id)
        merged[canonical] = _merge(merged.get(canonical), stat.count, stat.last_used)
    return merged


def _merge(prev: UsageStat | None, count: int, ts: str) -> UsageStat:
    if prev is None:
        return UsageStat(count=count, last_used=ts)
    return UsageStat(count=prev.count + count, last_used=max(prev.last_used, ts))
