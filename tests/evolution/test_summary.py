"""접힌 사용 요약 IO 계약 — 오래된 이벤트의 누적 보존.

  ① save→load round-trip: entries + compacted_through 보존
  ② 없는 파일 load = 빈 요약(entries {}, compacted_through None) — 첫 실행 안전
  ③ 빈 요약도 저장·복원된다
  ④ 깨진 파일은 빈 요약으로 폴백한다(usage는 버려도 되는 레이어 — 무한성장보다 안전)
  ⑤ 저장은 원자적 — 쓰다 죽어도 기존 요약이 반쯤 덮이지 않는다
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.aggregate import UsageStat
from pouch.evolution.summary import UsageSummary, load_summary, save_summary


def test_contract1_round_trip_preserves_entries_and_marker(tmp_path: Path) -> None:
    path = tmp_path / "usage-summary.json"
    summary = UsageSummary(
        entries={
            "aws-iam": UsageStat(count=40, last_used="2026-01-10T09:00:00"),
            "aws-cdk": UsageStat(count=12, last_used="2026-02-01T14:00:00"),
        },
        compacted_through="2026-03-01T00:00:00",
    )

    save_summary(summary, path=path)
    loaded = load_summary(path=path)

    assert loaded == summary
    assert loaded.entries["aws-iam"].count == 40
    assert loaded.compacted_through == "2026-03-01T00:00:00"


def test_contract2_missing_file_is_empty_summary(tmp_path: Path) -> None:
    loaded = load_summary(path=tmp_path / "nope.json")

    assert loaded.entries == {}
    assert loaded.compacted_through is None


def test_contract3_empty_summary_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "usage-summary.json"
    save_summary(UsageSummary(entries={}), path=path)

    loaded = load_summary(path=path)

    assert loaded.entries == {}
    assert loaded.compacted_through is None


def test_contract4_corrupt_file_falls_back_to_empty(tmp_path: Path) -> None:
    path = tmp_path / "usage-summary.json"
    path.write_text("{ this is not valid json", encoding="utf-8")

    loaded = load_summary(path=path)

    assert loaded.entries == {}
    assert loaded.compacted_through is None


def test_contract5_save_is_atomic_no_partial_temp(tmp_path: Path) -> None:
    path = tmp_path / "usage-summary.json"
    save_summary(UsageSummary(entries={"a": UsageStat(count=1, last_used="2026-01-01T00:00:00")}), path=path)

    # 임시 파일 잔재가 남지 않는다(원자적 교체)
    assert path.exists()
    assert not list(tmp_path.glob("*.tmp"))
