"""`pouch` 민낯 상태 화면 계약 — Phase 4.6 ②: 가시성.

  ① build_status: 카탈로그를 ownership별로 세고 표면(active) 수를 센다(순수)
  ② 최근 창(7일) 밖의 오래된 사용은 최근 집계에서 빠진다
  ③ 최근 사용 top은 횟수 내림차순, 동률이면 id 순
  ④ 카탈로그 밖에서 쓰인 도구가 outside_pouch로 잡힌다 (attach 신호의 표면)
  ⑤ 민낯 `pouch`: 주머니가 비어도 죽지 않고 채우는 법을 안내한다
  ⑥ 민낯 `pouch`: 담긴 것·최근 사용이 실제로 화면에 보인다
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pouch.catalog.model import ToolEntry, ToolKind
from pouch.cli import app
from pouch.evolution.usage_log import UsageEvent
from pouch.status import build_status

runner = CliRunner()

_NOW = "2026-07-02T12:00:00"


def _vendored(entry_id: str) -> ToolEntry:
    return ToolEntry.vendored(
        id=entry_id, kind=ToolKind.SKILL, source="t", title=entry_id,
        description="", upstream=f"/up/{entry_id}/SKILL.md",
    )


def _linked(entry_id: str) -> ToolEntry:
    return ToolEntry.linked(
        id=entry_id, kind=ToolKind.MCP, source="t", title=entry_id,
        description="", recipe={"command": "x"},
    )


def _event(entry_id: str, ts: str) -> UsageEvent:
    return UsageEvent(entry_id=entry_id, ts=ts)


def test_contract1_counts_ownership_and_surface() -> None:
    entries = [_vendored("a"), _vendored("b"), _linked("c")]

    status = build_status(
        memory_count=3, entries=entries, active_ids={"a"},
        events=[], now=_NOW, hook_memory=True, hook_usage=False,
    )

    assert status.catalog_total == 3
    assert status.vendored == 2 and status.linked == 1 and status.owned == 0
    assert status.active_count == 1
    assert status.memory_count == 3


def test_contract2_recent_window_excludes_old_events() -> None:
    events = [
        _event("fresh", "2026-07-01T09:00:00"),
        _event("ancient", "2026-01-01T09:00:00"),  # 창 밖
    ]

    status = build_status(
        memory_count=0, entries=[], active_ids=set(),
        events=events, now=_NOW, hook_memory=False, hook_usage=False,
    )

    ids = [entry_id for entry_id, _count in status.recent_top]
    assert "fresh" in ids
    assert "ancient" not in ids


def test_contract3_recent_top_sorted_by_count() -> None:
    events = [
        _event("twice", "2026-07-01T09:00:00"),
        _event("twice", "2026-07-01T10:00:00"),
        _event("once", "2026-07-01T11:00:00"),
    ]

    status = build_status(
        memory_count=0, entries=[], active_ids=set(),
        events=events, now=_NOW, hook_memory=False, hook_usage=False,
    )

    assert status.recent_top[0] == ("twice", 2)
    assert status.recent_top[1] == ("once", 1)


def test_contract4_outside_pouch_is_used_but_uncataloged() -> None:
    events = [
        _event("in-pouch", "2026-07-01T09:00:00"),
        _event("stranger", "2026-07-01T09:00:00"),
    ]

    status = build_status(
        memory_count=0, entries=[_vendored("in-pouch")], active_ids=set(),
        events=events, now=_NOW, hook_memory=False, hook_usage=False,
    )

    assert status.outside_pouch == ("stranger",)


def test_contract5_bare_pouch_guides_when_empty() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "catalog import" in result.output  # 빈 주머니면 채우는 법 안내


def test_contract6_bare_pouch_shows_catalog_and_usage(tmp_path: Path) -> None:
    skill = tmp_path / "aws-iam" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: aws-iam\ndescription: d\n---\nB\n", encoding="utf-8")
    runner.invoke(app, ["catalog", "import", str(skill)])
    import json

    payload = json.dumps({"tool_name": "Skill", "tool_input": {"skill": "aws-iam"}})
    runner.invoke(app, ["evolve", "log"], input=payload)

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "aws-iam" in result.output  # 최근 사용이 보인다
    assert "1" in result.output
