"""세션 쪽지 조립 계약 검증 — 모든 조각이 만나는 자리(장부+렌더러+물러남+구역).

정책([[pouch-proactive-nudge-policy]] 조각 4b): 쪽지를 통로에 실제로 실어보낸다.
build_session_note가 장부(조각1)를 읽어 물러남(조각4a)을 판정하고, 심을 때만
텍스트(조각3)를 내며 장부에 record_shown 한다.

핵심 안전: 심은 것만 장부에 기록한다(침묵은 장부를 안 건드림 — 유령 기록 방지).
기록 실패는 쪽지를 안 내보낸다(기록 못 하면 안 보임 — 간격 추적 깨짐 방지 비대칭).

  ① 문턱 미달 → "" + 장부 불변(유령 기록 없음)
  ② 첫 노출 → 텍스트 + 장부에 shown_count=1 기록
  ③ 방금 심었으면 재호출해도 "" (간격 물러남)
  ④ 간격 넘기면 다시 심고 shown_count 누적
  ⑤ gather_nudge_summary: 빈 환경 → 전부 0 (크래시 없음)
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.nudge import NudgePolicy, NudgeSummary
from pouch.evolution.ledger import shown_count
from pouch.evolution.session_nudge import build_session_note, gather_nudge_summary


def _summary(drop: int = 0, memory: int = 0) -> NudgeSummary:
    return NudgeSummary(drop_count=drop, reattach_count=0, adopt_count=0, memory_count=memory)


def test_contract1_below_threshold_leaves_ledger_untouched(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"

    note = build_session_note(
        _summary(), now="2026-07-09T00:00:00", ledger_path=ledger, policy=NudgePolicy()
    )

    assert note == ""
    # 침묵은 장부를 안 건드린다 — 유령 기록 없음
    assert shown_count("cleanup", ledger_path=ledger) == 0
    assert not ledger.exists()


def test_contract2_first_show_records_once(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"

    note = build_session_note(
        _summary(drop=2), now="2026-07-09T00:00:00", ledger_path=ledger, policy=NudgePolicy()
    )

    assert "정리하자" in note
    assert shown_count("cleanup", ledger_path=ledger) == 1


def test_contract3_immediate_recall_is_silent(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"
    build_session_note(
        _summary(drop=2), now="2026-07-09T00:00:00", ledger_path=ledger, policy=NudgePolicy()
    )

    # 같은 날 다시 세션 열림 → 간격 미달로 침묵
    second = build_session_note(
        _summary(drop=2), now="2026-07-09T06:00:00", ledger_path=ledger, policy=NudgePolicy()
    )

    assert second == ""
    # 안 보였으니 count도 그대로 1
    assert shown_count("cleanup", ledger_path=ledger) == 1


def test_contract4_after_interval_shows_and_accumulates(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"
    policy = NudgePolicy(base_interval_days=3)
    build_session_note(
        _summary(drop=2), now="2026-07-01T00:00:00", ledger_path=ledger, policy=policy
    )

    # 8일 뒤 → 간격(3일) 넘겨 다시 심음
    later = build_session_note(
        _summary(drop=2), now="2026-07-09T00:00:00", ledger_path=ledger, policy=policy
    )

    assert "정리하자" in later
    assert shown_count("cleanup", ledger_path=ledger) == 2


def test_contract5_gather_empty_env_is_all_zero() -> None:
    # 빈 환경(격리된 tmp home)에서 계획 수집이 크래시 없이 전부 0
    summary = gather_nudge_summary(now="2026-07-09T00:00:00")

    assert summary.total == 0
