"""접기 순수 함수 계약 — 경계 밖 이벤트를 누적으로 접는다(무손실·멱등).

  ① 경계 밖은 요약으로 접히고(count 합산), 경계 안은 남는다(recent_keep)
  ② compacted_through가 접은 경계(cutoff)로 전진한다
  ③ 기존 요약에 누적된다(덮어쓰기 아니라 더하기)
  ④ 멱등: 이미 접힌 구간(ts <= compacted_through)은 다시 접지 않는다
  ⑤ 접을 게 없으면(모두 최근) 요약 불변, 전부 남는다
  ⑥ now·after_days 주입 — 순수(시계 없음)
"""

from __future__ import annotations

from pouch.evolution.aggregate import UsageStat
from pouch.evolution.compaction import compact, full_stats
from pouch.evolution.summary import UsageSummary
from pouch.evolution.usage_log import UsageEvent

_AFTER = 180


def _ev(entry_id: str, ts: str) -> UsageEvent:
    return UsageEvent(entry_id=entry_id, ts=ts)


def test_contract1_folds_old_keeps_recent() -> None:
    events = [
        _ev("aws-iam", "2026-01-01T10:00:00"),  # 오래됨(경계 밖)
        _ev("aws-iam", "2026-01-05T10:00:00"),  # 오래됨
        _ev("aws-cdk", "2026-07-06T10:00:00"),  # 최근(경계 안)
    ]

    new_summary, recent = compact(events, UsageSummary(), now="2026-07-07T00:00:00", after_days=_AFTER)

    # 오래된 aws-iam 2회가 요약으로 접힘
    assert new_summary.entries["aws-iam"].count == 2
    assert new_summary.entries["aws-iam"].last_used == "2026-01-05T10:00:00"
    # 최근 aws-cdk는 남고 요약엔 없음
    assert "aws-cdk" not in new_summary.entries
    assert [e.entry_id for e in recent] == ["aws-cdk"]


def test_contract2_marker_advances_to_cutoff() -> None:
    events = [_ev("a", "2026-01-01T10:00:00")]

    new_summary, _ = compact(events, UsageSummary(), now="2026-07-07T00:00:00", after_days=_AFTER)

    # cutoff = 2026-07-07 - 180일 = 2026-01-08
    assert new_summary.compacted_through == "2026-01-08T00:00:00"


def test_contract3_accumulates_onto_existing_summary() -> None:
    existing = UsageSummary(
        entries={"aws-iam": UsageStat(count=40, last_used="2025-12-01T00:00:00")},
        compacted_through="2025-12-15T00:00:00",
    )
    events = [_ev("aws-iam", "2026-01-01T10:00:00")]  # 새로 접힐 오래된 이벤트

    new_summary, _ = compact(events, existing, now="2026-07-07T00:00:00", after_days=_AFTER)

    # 40 + 1 = 41 (누적)
    assert new_summary.entries["aws-iam"].count == 41
    assert new_summary.entries["aws-iam"].last_used == "2026-01-01T10:00:00"


def test_contract4_idempotent_skips_already_folded() -> None:
    existing = UsageSummary(
        entries={"a": UsageStat(count=5, last_used="2025-12-01T00:00:00")},
        compacted_through="2026-01-08T00:00:00",
    )
    # 이미 접힌 구간(compacted_through 이하)에 남아있는 이벤트 — 재작성 실패 잔재라 가정
    events = [_ev("a", "2025-12-20T00:00:00")]  # <= compacted_through

    new_summary, recent = compact(events, existing, now="2026-07-07T00:00:00", after_days=_AFTER)

    # 이미 접힌 것이라 count 안 늘어남(이중 계산 방지)
    assert new_summary.entries["a"].count == 5
    # recent에도 안 남긴다(공간 회수 — 이미 접힌 잔재)
    assert recent == []


def test_contract5_nothing_old_leaves_summary_untouched() -> None:
    events = [_ev("a", "2026-07-06T10:00:00"), _ev("b", "2026-07-05T10:00:00")]

    new_summary, recent = compact(events, UsageSummary(), now="2026-07-07T00:00:00", after_days=_AFTER)

    assert new_summary.entries == {}
    assert new_summary.compacted_through is None  # 접은 게 없으면 마커도 안 세운다
    assert len(recent) == 2


# ── full_stats: 요약 + 최근 상세를 합쳐 "전체 통계"를 낸다 ──


def test_full_stats_summary_only() -> None:
    summary = UsageSummary(entries={"a": UsageStat(count=40, last_used="2026-01-01T00:00:00")})

    stats = full_stats(summary, [])

    assert stats["a"].count == 40


def test_full_stats_events_only_matches_plain_aggregate() -> None:
    events = [_ev("a", "2026-07-01T00:00:00"), _ev("a", "2026-07-02T00:00:00")]

    stats = full_stats(UsageSummary(), events)

    assert stats["a"].count == 2
    assert stats["a"].last_used == "2026-07-02T00:00:00"


def test_full_stats_merges_summary_and_recent() -> None:
    summary = UsageSummary(entries={"a": UsageStat(count=40, last_used="2026-01-01T00:00:00")})
    events = [_ev("a", "2026-07-01T00:00:00")]

    stats = full_stats(summary, events)

    # 요약 40 + 최근 1 = 41, last_used는 최신
    assert stats["a"].count == 41
    assert stats["a"].last_used == "2026-07-01T00:00:00"


def test_full_stats_ignores_already_folded_leftovers() -> None:
    summary = UsageSummary(
        entries={"a": UsageStat(count=5, last_used="2025-12-01T00:00:00")},
        compacted_through="2026-01-08T00:00:00",
    )
    # jsonl에 접힌 잔재가 남아있어도(재작성 실패) 이중 계산하지 않는다
    events = [_ev("a", "2025-12-20T00:00:00")]  # <= compacted_through

    stats = full_stats(summary, events)

    assert stats["a"].count == 5  # 잔재 무시(이중 계산 방지)
