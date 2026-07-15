"""핵심 도구 인식 — 순수 판정 + evolve drop 보호 통합."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pouch.evolution.core_tools import core_entry_ids
from pouch.evolution.usage_log import UsageEvent


def _uses(entry_id: str, count: int, first: str, last: str) -> list[UsageEvent]:
    """count개 이벤트 — first·last를 양끝으로, 나머지는 first에 쌓는다."""
    evs = [UsageEvent(entry_id=entry_id, ts=first), UsageEvent(entry_id=entry_id, ts=last)]
    evs += [UsageEvent(entry_id=entry_id, ts=first) for _ in range(max(0, count - 2))]
    return evs


# ── 순수 판정 ────────────────────────────────────────────────────────────


def test_core_when_frequent_and_sustained() -> None:
    # 12회 + span 30일 → 핵심(손에 맞음).
    evs = _uses("alpha", 12, "2026-06-01T00:00:00", "2026-07-01T00:00:00")
    assert core_entry_ids(evs) == {"alpha"}


def test_burst_is_not_core() -> None:
    # 12회지만 span 3일 → burst(몰아쓰고 끝), 핵심 아님.
    evs = _uses("alpha", 12, "2026-07-01T00:00:00", "2026-07-04T00:00:00")
    assert core_entry_ids(evs) == set()


def test_low_count_is_not_core() -> None:
    # span은 길지만 5회 → 핵심 아님.
    evs = _uses("alpha", 5, "2026-06-01T00:00:00", "2026-07-01T00:00:00")
    assert core_entry_ids(evs) == set()


def test_alias_folding_reaches_threshold() -> None:
    # exa 6회 + plugin_x_exa 6회 = 접으면 12회·span 김 → 핵심(안 접으면 각 6<10).
    evs = _uses("exa", 6, "2026-06-01T00:00:00", "2026-06-20T00:00:00")
    evs += _uses("plugin_x_exa", 6, "2026-06-25T00:00:00", "2026-07-05T00:00:00")
    assert core_entry_ids(evs, alias_map={"plugin_x_exa": "exa"}) == {"exa"}
    assert core_entry_ids(evs) == set()  # 안 접으면 아무것도 핵심 아님


# ── evolve drop 보호(통합) ───────────────────────────────────────────────


def _skill_md(entry_id: str) -> str:
    return (
        f"---\nid: {entry_id}\nkind: skill\nownership: owned\n"
        f"source: t\ntitle: {entry_id}\ndescription: d\n---\n본문\n"
    )


def test_evolve_protects_core_tool_but_suggests_straggler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from typer.testing import CliRunner

    from pouch.cli import app

    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "veteran.md").write_text(_skill_md("veteran"), encoding="utf-8")
    (tmp_path / "catalog" / "straggler.md").write_text(_skill_md("straggler"), encoding="utf-8")

    now = datetime.now()

    def ago(days: int) -> str:
        return (now - timedelta(days=days)).isoformat(timespec="seconds")

    # 둘 다 오래전 설치(유예 지남)·마지막 사용 35일 전(stale). 차이는 핵심 여부.
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "veteran": {"status": "active", "installed_at": ago(90)},
                "straggler": {"status": "active", "installed_at": ago(90)},
            }
        ),
        encoding="utf-8",
    )
    # veteran: 12회·span 25일 → 핵심(보호). straggler: 2회 → 핵심 아님(제안).
    events = _uses("veteran", 12, ago(60), ago(35)) + _uses("straggler", 2, ago(36), ago(35))
    (tmp_path / "usage.jsonl").write_text(
        "\n".join(json.dumps({"entry_id": e.entry_id, "ts": e.ts}) for e in events) + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["evolve", "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "straggler" in result.stdout  # 핵심 아닌 stale은 정리 제안됨
    assert "veteran" not in result.stdout  # 핵심은 보호돼 제안에서 빠짐
