"""usage 집계 계약 검증 — 이벤트 스트림 → entry_id별 통계.

신호 정책: 최근성 주축(last_used) + 횟수 보조(count). 순수 함수.
ISO8601 문자열은 사전식 비교가 곧 시간순이라 last_used = max(ts).

  ① 같은 entry_id는 접힌다 — count 누적, last_used는 최신 ts
  ② 여러 entry_id는 각각 집계된다
  ③ 빈 이벤트 → 빈 집계
  ④ last_used는 적재 순서와 무관하게 최신 ts (뒤늦게 옛 ts가 와도 안 밀림)
"""

from __future__ import annotations

from pouch.evolution.aggregate import aggregate_usage
from pouch.evolution.usage_log import UsageEvent


def test_contract1_same_id_folds_count_and_latest_ts() -> None:
    events = [
        UsageEvent("aws-iam", "2026-07-01T10:00:00"),
        UsageEvent("aws-iam", "2026-07-01T12:00:00"),
        UsageEvent("aws-iam", "2026-07-01T11:00:00"),
    ]

    stats = aggregate_usage(events)

    assert stats["aws-iam"].count == 3
    assert stats["aws-iam"].last_used == "2026-07-01T12:00:00"


def test_contract2_distinct_ids_aggregated_separately() -> None:
    events = [
        UsageEvent("a", "2026-07-01T10:00:00"),
        UsageEvent("b", "2026-07-01T10:00:00"),
        UsageEvent("a", "2026-07-01T11:00:00"),
    ]

    stats = aggregate_usage(events)

    assert stats["a"].count == 2
    assert stats["b"].count == 1


def test_contract3_empty_events_empty_stats() -> None:
    assert aggregate_usage([]) == {}


def test_contract4_last_used_is_max_regardless_of_order() -> None:
    events = [
        UsageEvent("x", "2026-07-01T15:00:00"),
        UsageEvent("x", "2026-07-01T09:00:00"),  # 뒤늦게 온 옛 ts
    ]

    stats = aggregate_usage(events)

    assert stats["x"].last_used == "2026-07-01T15:00:00"
    assert stats["x"].count == 2
