"""run_compaction IO 통합 — 요약 저장 + 로그 재작성 왕복·멱등.

  ① 오래된 이벤트는 요약 파일로 접히고 로그엔 최근만 남는다
  ② 접힌 줄 수를 반환한다
  ③ 멱등: 다시 실행하면 접을 게 없어 0을 반환하고 파일이 안 바뀐다
  ④ 접힌 뒤에도 plan_evolution 통계가 과거 사용을 안다(never-used 오분류 방지)
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.candidates import EvolveConfig
from pouch.evolution.orchestrate import plan_evolution, run_compaction
from pouch.evolution.state import record_installed
from pouch.evolution.summary import load_summary
from pouch.evolution.usage_log import UsageEvent, append_event, read_events

_NOW = "2026-07-07T00:00:00"
_AFTER = 180


def _seed(log: Path) -> None:
    # 오래된 2건(경계 밖) + 최근 1건(경계 안)
    append_event(UsageEvent("aws-iam", "2026-01-01T10:00:00"), log_path=log)
    append_event(UsageEvent("aws-iam", "2026-01-05T10:00:00"), log_path=log)
    append_event(UsageEvent("aws-cdk", "2026-07-06T10:00:00"), log_path=log)


def test_folds_old_into_summary_and_shrinks_log(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    summary_path = tmp_path / "usage-summary.json"
    _seed(log)

    folded = run_compaction(now=_NOW, after_days=_AFTER, usage_path=log, summary_path=summary_path)

    assert folded == 2
    # 로그엔 최근만
    assert [e.entry_id for e in read_events(log_path=log)] == ["aws-cdk"]
    # 요약에 오래된 aws-iam 2회 누적
    summary = load_summary(path=summary_path)
    assert summary.entries["aws-iam"].count == 2


def test_idempotent_second_run_folds_nothing(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    summary_path = tmp_path / "usage-summary.json"
    _seed(log)
    run_compaction(now=_NOW, after_days=_AFTER, usage_path=log, summary_path=summary_path)

    folded_again = run_compaction(now=_NOW, after_days=_AFTER, usage_path=log, summary_path=summary_path)

    assert folded_again == 0
    assert load_summary(path=summary_path).entries["aws-iam"].count == 2  # 이중 계산 없음


def test_plan_evolution_knows_folded_past(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    summary_path = tmp_path / "usage-summary.json"
    state = tmp_path / "state.json"
    # aws-iam을 설치해 두고, 오래전에만 썼다(접힐 것) → stale이어야지 never-used면 안 됨
    record_installed("aws-iam", now="2025-12-01T00:00:00", state_path=state)
    append_event(UsageEvent("aws-iam", "2026-01-01T10:00:00"), log_path=log)
    run_compaction(now=_NOW, after_days=_AFTER, usage_path=log, summary_path=summary_path)

    drops = plan_evolution(
        now=_NOW, config=EvolveConfig(),
        usage_path=log, state_path=state, summary_path=summary_path,
    )

    # 접힌 뒤에도 "썼던 도구"로 인식 — 후보 사유가 never-used가 아니어야 한다
    iam = [d for d in drops if d.entry_id == "aws-iam"]
    assert iam and iam[0].reason != "never-used"
