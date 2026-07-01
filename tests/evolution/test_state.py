"""활성 표면 상태 사이드카 계약 검증 — install/drop 라이프사이클 기록.

정책: 상태 저장은 사이드카 분리. `~/.pouch/state.json`(entry_id → installed_at·status).
카탈로그(레지스트리)와 분리 — churn 데이터가 overlay/body와 안 엉킨다.
"떨어진다 ≠ 삭제된다"의 상태 표현: drop은 status=dropped일 뿐, 기록은 남는다.

  ① record_installed: installed_at + status=active
  ② active_entries: status=active만 {entry_id: installed_at}
  ③ mark_dropped: status=dropped, installed_at 기록은 보존
  ④ 재부착(record_installed 재호출): installed_at 갱신 + 다시 active
  ⑤ 없는 상태 파일 → 빈 active (첫 실행 안전)
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.state import (
    active_entries,
    mark_dropped,
    record_installed,
)


def test_contract1_record_installed_sets_active(tmp_path: Path) -> None:
    state = tmp_path / "state.json"

    record_installed("aws-iam", now="2026-07-01T00:00:00", state_path=state)

    assert active_entries(state_path=state) == {"aws-iam": "2026-07-01T00:00:00"}


def test_contract2_active_excludes_dropped(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    record_installed("a", now="2026-07-01T00:00:00", state_path=state)
    record_installed("b", now="2026-07-01T00:00:00", state_path=state)

    mark_dropped("a", state_path=state)

    assert active_entries(state_path=state) == {"b": "2026-07-01T00:00:00"}


def test_contract3_drop_preserves_installed_record(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    record_installed("a", now="2026-07-01T00:00:00", state_path=state)

    mark_dropped("a", state_path=state)

    # active엔 없지만 기록은 남는다 (재추천 금지 판단의 근거)
    from pouch.evolution.state import load_state

    assert load_state(state_path=state)["a"]["status"] == "dropped"
    assert load_state(state_path=state)["a"]["installed_at"] == "2026-07-01T00:00:00"


def test_contract4_reattach_refreshes_and_reactivates(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    record_installed("a", now="2026-06-01T00:00:00", state_path=state)
    mark_dropped("a", state_path=state)

    # 재부착 = installed_at 갱신 + 다시 active (never-used 시계 리셋)
    record_installed("a", now="2026-07-01T00:00:00", state_path=state)

    assert active_entries(state_path=state) == {"a": "2026-07-01T00:00:00"}


def test_contract5_missing_state_is_empty(tmp_path: Path) -> None:
    assert active_entries(state_path=tmp_path / "nope.json") == {}
