"""제안 장부 사이드카 계약 검증 — 먼저 내미는 제안의 "언제·몇 번 심었나".

정책([[pouch-proactive-nudge-policy]]): 잔소리 방어(간격·묵히기)는 작은 상태를
요구한다 — "이 제안 언제 심었나 / 몇 번째인가". usage.jsonl 옆 사이드카
(`~/.pouch/proposals.json`), state.json과 같은 정신(버려도 되는 층, now 주입).

정밀화가 이긴다: 묵히기는 *반자동*이라 명시 스누즈("언제까지 묵혀달라")는
저장하지 않는다. 장부는 심은 사실만 기록하고, "물러남"(조각 4)이 이 위에서
last_shown_at·shown_count로 유효 침묵 구간을 계산한다.

  ① record_shown: last_shown_at 갱신 + shown_count 증가
  ② last_shown: 심은 적 없으면 None, 있으면 마지막 시각
  ③ shown_count: 심은 적 없으면 0, 반복하면 누적
  ④ 여러 제안은 proposal_id로 독립 기록
  ⑤ 없는 장부 파일 → 빈 상태 (첫 실행 안전)
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.ledger import (
    last_shown,
    load_ledger,
    record_shown,
    shown_count,
)


def test_contract1_record_shown_stamps_time_and_counts(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"

    record_shown("adopt:aws-iam", now="2026-07-09T00:00:00", ledger_path=ledger)

    assert last_shown("adopt:aws-iam", ledger_path=ledger) == "2026-07-09T00:00:00"
    assert shown_count("adopt:aws-iam", ledger_path=ledger) == 1


def test_contract2_last_shown_none_when_never(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"

    assert last_shown("adopt:never", ledger_path=ledger) is None


def test_contract3_shown_count_accumulates(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"
    record_shown("adopt:aws-iam", now="2026-07-01T00:00:00", ledger_path=ledger)
    record_shown("adopt:aws-iam", now="2026-07-05T00:00:00", ledger_path=ledger)
    record_shown("adopt:aws-iam", now="2026-07-09T00:00:00", ledger_path=ledger)

    # 마지막 시각으로 갱신, 횟수는 누적
    assert last_shown("adopt:aws-iam", ledger_path=ledger) == "2026-07-09T00:00:00"
    assert shown_count("adopt:aws-iam", ledger_path=ledger) == 3


def test_contract4_proposals_are_independent(tmp_path: Path) -> None:
    ledger = tmp_path / "proposals.json"
    record_shown("adopt:aws-iam", now="2026-07-01T00:00:00", ledger_path=ledger)
    record_shown("adopt:terraform", now="2026-07-09T00:00:00", ledger_path=ledger)
    record_shown("adopt:terraform", now="2026-07-09T00:00:00", ledger_path=ledger)

    assert shown_count("adopt:aws-iam", ledger_path=ledger) == 1
    assert shown_count("adopt:terraform", ledger_path=ledger) == 2


def test_contract5_missing_ledger_is_empty(tmp_path: Path) -> None:
    assert load_ledger(ledger_path=tmp_path / "nope.json") == {}
    assert shown_count("anything", ledger_path=tmp_path / "nope.json") == 0
    assert last_shown("anything", ledger_path=tmp_path / "nope.json") is None
