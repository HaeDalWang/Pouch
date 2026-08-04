"""사이드카 IO 계약 검증 — 사용 이벤트 append-only 로그.

  ① append_event: 한 줄씩 JSONL로 덧붙인다 (기존 줄 보존)
  ② read_events: 적재 순서대로 UsageEvent를 돌려준다
  ③ 로그가 없으면 read는 빈 리스트 (첫 실행 안전)
  ④ 빈 줄/깨진 줄은 건너뛴다 (append 도중 죽어도 나머지 유효)
  ⑤ ts는 주입 — 로그는 시계를 만들지 않는다 (결정적)
  ⑥ host(어느 표면에서 왔나)는 있으면 싣고 없으면 아예 안 싣는다 — 옛 줄과 같은 꼴
  ⑦ host 없는 옛 줄도 읽힌다 (모름 = None, 소급 거짓말 안 함)
  ⑧ session(한 세션 묶음)도 같은 규칙 — 있으면 싣고, 없으면 모름
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.usage_log import UsageEvent, append_event, read_events


def test_contract1_append_preserves_prior_lines(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"

    append_event(UsageEvent(entry_id="aws-iam", ts="2026-07-01T10:00:00"), log_path=log)
    append_event(UsageEvent(entry_id="aws-cdk", ts="2026-07-01T10:05:00"), log_path=log)

    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "aws-iam" in lines[0]
    assert "aws-cdk" in lines[1]


def test_contract2_read_returns_events_in_order(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    append_event(UsageEvent(entry_id="a", ts="2026-07-01T10:00:00"), log_path=log)
    append_event(UsageEvent(entry_id="b", ts="2026-07-01T11:00:00"), log_path=log)

    events = read_events(log_path=log)

    assert [e.entry_id for e in events] == ["a", "b"]
    assert events[0].ts == "2026-07-01T10:00:00"


def test_contract3_missing_log_reads_empty(tmp_path: Path) -> None:
    assert read_events(log_path=tmp_path / "nope.jsonl") == []


def test_contract4_skips_blank_and_broken_lines(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    log.write_text(
        '{"entry_id": "ok1", "ts": "2026-07-01T10:00:00"}\n'
        "\n"
        "{broken json\n"
        '{"entry_id": "ok2", "ts": "2026-07-01T10:01:00"}\n',
        encoding="utf-8",
    )

    events = read_events(log_path=log)

    assert [e.entry_id for e in events] == ["ok1", "ok2"]


def test_contract5_append_creates_parent_dir(tmp_path: Path) -> None:
    log = tmp_path / "deep" / "nested" / "usage.jsonl"

    append_event(UsageEvent(entry_id="x", ts="2026-07-01T10:00:00"), log_path=log)

    assert log.exists()
    assert read_events(log_path=log)[0].entry_id == "x"


def test_contract6_host_is_carried_when_present(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"

    append_event(
        UsageEvent(entry_id="aws-iam", ts="2026-08-04T10:00:00", host="claude"),
        log_path=log,
    )

    assert '"host": "claude"' in log.read_text(encoding="utf-8")
    assert read_events(log_path=log)[0].host == "claude"


def test_contract6_host_absent_keeps_old_shape(tmp_path: Path) -> None:
    """host를 모르면 빈 값을 싣지 않는다 — 옛 줄과 글자까지 같은 꼴."""
    log = tmp_path / "usage.jsonl"

    append_event(UsageEvent(entry_id="aws-iam", ts="2026-08-04T10:00:00"), log_path=log)

    assert "host" not in log.read_text(encoding="utf-8")


def test_contract8_session_is_carried_when_present(tmp_path: Path) -> None:
    """같은 세션에서 뭘 같이 썼는지는 이 칸으로만 묶인다."""
    log = tmp_path / "usage.jsonl"

    append_event(
        UsageEvent(entry_id="aws-iam", ts="2026-08-04T10:00:00", session_id="s-1"),
        log_path=log,
    )
    append_event(
        UsageEvent(entry_id="terraform", ts="2026-08-04T10:01:00", session_id="s-1"),
        log_path=log,
    )

    events = read_events(log_path=log)
    assert [e.session_id for e in events] == ["s-1", "s-1"]


def test_contract8_session_absent_keeps_old_shape(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"

    append_event(UsageEvent(entry_id="aws-iam", ts="2026-08-04T10:00:00"), log_path=log)

    assert "session_id" not in log.read_text(encoding="utf-8")


def test_contract7_old_lines_without_host_read_as_unknown(tmp_path: Path) -> None:
    """이미 쌓인 기록은 출처가 없다 — 지어내지 않고 '모름'으로 읽는다."""
    log = tmp_path / "usage.jsonl"
    log.write_text(
        '{"entry_id": "old", "ts": "2026-07-01T10:00:00"}\n'
        '{"entry_id": "new", "ts": "2026-08-04T10:00:00", "host": "codex"}\n',
        encoding="utf-8",
    )

    events = read_events(log_path=log)

    assert events[0].host is None
    assert events[1].host == "codex"
