"""접기(compaction) 순수 함수 — 경계 밖 이벤트를 누적으로 접는다.

무손실: 개별 시각은 버리되 entry_id별 누적 횟수는 요약에 더한다(습관 신호 보존).
멱등: 이미 접힌 구간(compacted_through 이하)은 다시 접지 않는다 — jsonl 재작성이
실패해 접힌 잔재가 남아도 이중 계산되지 않는다.

now·after_days는 주입한다 — 코어는 시계를 만들지 않는다(결정적 테스트).
경계 규칙: cutoff = now - after_days. cutoff *이하*는 접고(과거), cutoff 초과는
남긴다(최근). 접힌 경계(compacted_through)와 남길 창(recent)이 정확히 맞물린다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pouch.evolution.aggregate import UsageStat
from pouch.evolution.summary import UsageSummary
from pouch.evolution.usage_log import UsageEvent

# 이보다 오래된 이벤트를 요약으로 접는다. 진화 최대 판단 창(stale 30일)보다 훨씬
# 밖이라 접어도 판단 무손실. 6개월 — 상세를 오래 보관하되(습관 요약은 영구).
DEFAULT_COMPACT_AFTER_DAYS = 180


def _add(stats: dict[str, UsageStat], entry_id: str, count: int, ts: str) -> None:
    """stats에 (count, ts)를 누적한다(in-place 헬퍼 — 지역 dict에만 사용)."""
    prev = stats.get(entry_id)
    if prev is None:
        stats[entry_id] = UsageStat(count=count, last_used=ts)
    else:
        stats[entry_id] = UsageStat(
            count=prev.count + count, last_used=max(prev.last_used, ts)
        )


def full_stats(summary: UsageSummary, events: list[UsageEvent]) -> dict[str, UsageStat]:
    """접힌 요약 + 최근 상세를 합쳐 entry_id별 전체 통계를 낸다(순수).

    compacted_through 이하 이벤트(이미 접힌 잔재)는 무시해 이중 계산을 막는다.
    drop 후보 판단이 "200일 전 썼던 도구"를 never-used로 오분류하지 않게 한다.
    """
    result = dict(summary.entries)
    through = summary.compacted_through
    for event in events:
        if through is not None and event.ts <= through:
            continue  # 이미 접힘 — 잔재 무시(멱등)
        _add(result, event.entry_id, 1, event.ts)
    return result


def compact(
    events: list[UsageEvent],
    summary: UsageSummary,
    *,
    now: str,
    after_days: int,
) -> tuple[UsageSummary, list[UsageEvent]]:
    """경계 밖 이벤트를 요약에 접고, 남길 최근 이벤트를 함께 돌려준다.

    반환: (갱신된 요약, jsonl에 남길 최근 이벤트). 접을 게 없으면 요약은 불변.
    """
    cutoff = (datetime.fromisoformat(now) - timedelta(days=after_days)).isoformat()
    already = summary.compacted_through

    to_fold: list[UsageEvent] = []
    recent: list[UsageEvent] = []
    for event in events:
        if event.ts > cutoff:
            recent.append(event)  # 최근 — 상세 유지
        elif already is None or event.ts > already:
            to_fold.append(event)  # 경계 밖 + 아직 안 접힘 — 접는다
        # else: 이미 접힌 잔재(ts <= already) — 접지도 남기지도 않음(공간 회수, 멱등)

    if not to_fold:
        # 새로 접은 게 없으면 마커도 건드리지 않는다(멱등·불변).
        return summary, recent

    folded_entries = dict(summary.entries)
    for event in to_fold:
        _add(folded_entries, event.entry_id, 1, event.ts)

    return UsageSummary(entries=folded_entries, compacted_through=cutoff), recent
