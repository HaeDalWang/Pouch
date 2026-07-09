"""물러남 계약 검증 — 무시엔 물러난다, 절대 조르지 않는다(장부 위 backoff).

정책([[pouch-proactive-nudge-policy]] 조각 4): 심은 게 무시되면 pouch가 더
조용해진다(같은 쪽지 덜 심기). 무시는 공짜 — 그냥 무시하는 게 곧 "지금 아님"
(반자동 묵히기, '나중에' 버튼 불필요).

핵심 불변식(키우기 금지): 무시된 쪽지가 다음에 더 크게·자주 뜨면 잔소리를 다른
이름으로 하는 것 → 물러남만 허용, 키우기 금지. backoff 간격이 shown_count에
대해 단조 비감소여야 한다(절대 짧아지지 않는다).

  ① 심은 적 없음(last_shown None) → 보인다(문턱 넘으면 조용한 쪽지 1개)
  ② 방금 심었으면(간격 미달) → 안 보인다(안 조름)
  ③ 간격을 넘겼으면 → 다시 보인다
  ④ 물러남 불변식: 간격은 shown_count에 대해 단조 비감소(짧아지지 않음)
  ⑤ 순수 함수 — now·last_shown·count 주입, 시계·IO 없음
"""

from __future__ import annotations

from pouch.evolution.nudge import (
    NudgePolicy,
    NudgeSummary,
    backoff_days,
    plan_nudge,
    should_nudge,
)


def test_contract1_never_shown_shows() -> None:
    # 심은 적 없으면 문턱 넘었을 때 무조건 한 번 심는다
    assert should_nudge(
        last_shown=None, shown_count=0, now="2026-07-09T00:00:00", policy=NudgePolicy()
    )


def test_contract2_just_shown_stays_quiet() -> None:
    # 방금(같은 날) 심었으면 다시 안 뜬다 — 안 조름
    assert not should_nudge(
        last_shown="2026-07-09T00:00:00",
        shown_count=1,
        now="2026-07-09T12:00:00",
        policy=NudgePolicy(),
    )


def test_contract3_after_interval_shows_again() -> None:
    # 간격(기본 3일)을 넘기면 다시 심을 수 있다
    policy = NudgePolicy(base_interval_days=3)
    assert should_nudge(
        last_shown="2026-07-01T00:00:00",
        shown_count=1,
        now="2026-07-09T00:00:00",  # 8일 경과 > 3일
        policy=policy,
    )


def test_contract4_backoff_is_monotonic_nondecreasing() -> None:
    # 물러남 불변식: 심을수록 간격이 커지기만 한다(절대 짧아지지 않음)
    policy = NudgePolicy()
    intervals = [backoff_days(count, policy) for count in range(1, 12)]

    for earlier, later in zip(intervals, intervals[1:]):
        assert later >= earlier, f"간격이 짧아졌다: {earlier} → {later} (키우기 금지 위반)"


def test_contract4b_more_ignores_means_longer_silence() -> None:
    # 구체: 많이 무시할수록(count 큼) 다음 쪽지까지 더 오래 침묵
    policy = NudgePolicy(base_interval_days=3)
    # 한 번 보고 무시한 상태 vs 다섯 번 보고 무시한 상태 — 같은 경과 시간
    seen_once_soon = should_nudge(
        last_shown="2026-07-05T00:00:00", shown_count=1,
        now="2026-07-09T00:00:00", policy=policy,  # 4일 경과
    )
    seen_many_soon = should_nudge(
        last_shown="2026-07-05T00:00:00", shown_count=5,
        now="2026-07-09T00:00:00", policy=policy,  # 같은 4일 경과
    )
    # 1번 봤으면 3일 간격 넘겨 다시 뜨지만, 5번 봤으면 아직 침묵(더 물러남)
    assert seen_once_soon
    assert not seen_many_soon


def test_contract5_decision_is_pure() -> None:
    args = dict(
        last_shown="2026-07-01T00:00:00", shown_count=2,
        now="2026-07-09T00:00:00", policy=NudgePolicy(),
    )
    assert should_nudge(**args) == should_nudge(**args)


def test_backoff_capped_at_max() -> None:
    # 물러남은 바닥 빈도로 수렴할 뿐 무한히 커지지 않는다(멈춤 아님, 드물게 유지)
    policy = NudgePolicy(base_interval_days=3, max_interval_days=30)
    assert backoff_days(100, policy) == 30


# plan_nudge — 잔소리 방어 4개가 한 곳에 모인다(문턱·간격·물러남·기본은 침묵)


def _summary(total_drop: int = 0, memory: int = 0) -> NudgeSummary:
    return NudgeSummary(
        drop_count=total_drop, reattach_count=0, adopt_count=0, memory_count=memory
    )


def test_plan_empty_summary_is_silent() -> None:
    # 문턱 미달(쌓인 것 0) → 심을 게 있어도(간격 통과) 침묵
    assert (
        plan_nudge(
            _summary(), last_shown=None, shown_count=0,
            now="2026-07-09T00:00:00", policy=NudgePolicy(),
        )
        == ""
    )


def test_plan_first_time_over_threshold_shows() -> None:
    # 쌓였고(문턱 통과) 심은 적 없음(간격 통과) → 쪽지 텍스트
    note = plan_nudge(
        _summary(total_drop=2), last_shown=None, shown_count=0,
        now="2026-07-09T00:00:00", policy=NudgePolicy(),
    )
    assert "정리하자" in note


def test_plan_recently_shown_is_silent() -> None:
    # 쌓였지만 방금 심음(간격 미달) → 침묵(안 조름)
    assert (
        plan_nudge(
            _summary(total_drop=2), last_shown="2026-07-09T00:00:00", shown_count=1,
            now="2026-07-09T06:00:00", policy=NudgePolicy(),
        )
        == ""
    )
