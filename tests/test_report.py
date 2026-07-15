"""`pouch report` — 기간별 주머니 리포트: 순수 집계 + 렌더 + CLI."""

from __future__ import annotations

from pouch.catalog.model import ToolEntry, ToolKind
from pouch.evolution.usage_log import UsageEvent
from pouch.report import build_report, render_report_lines


def _skill(entry_id: str) -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id, kind=ToolKind.SKILL, source="t", title=entry_id, description="d", body="b"
    )


def _hook(entry_id: str) -> ToolEntry:
    # 훅은 사용 신호가 안 찍히는 종류 — "닳는 중"에 안 잡혀야 한다.
    return ToolEntry.owned(
        id=entry_id, kind=ToolKind.HOOK, source="t", title=entry_id, description="d", body="b"
    )


NOW = "2026-07-15T12:00:00"


def _ev(entry_id: str, ts: str) -> UsageEvent:
    return UsageEvent(entry_id=entry_id, ts=ts)


def test_most_used_ranks_catalog_tools_by_count() -> None:
    entries = [_skill("alpha"), _skill("beta")]
    events = [
        _ev("alpha", "2026-07-14T10:00:00"),
        _ev("alpha", "2026-07-14T11:00:00"),
        _ev("beta", "2026-07-14T10:00:00"),
    ]
    report = build_report(
        entries=entries, active_ids={"alpha", "beta"}, events=events, now=NOW, window_days=7
    )
    assert report.total_uses == 3
    assert report.most_used == (("alpha", 2), ("beta", 1))


def test_idle_active_lists_unused_signal_tools_only() -> None:
    # alpha는 씀, beta는 안 씀(신호형→닳는 중), h는 훅(신호 없음→제외).
    entries = [_skill("alpha"), _skill("beta"), _hook("h")]
    events = [_ev("alpha", "2026-07-14T10:00:00")]
    report = build_report(
        entries=entries, active_ids={"alpha", "beta", "h"}, events=events, now=NOW, window_days=7
    )
    assert report.idle_active == ("beta",)  # 훅 h는 빠진다


def test_idle_only_counts_active_surface() -> None:
    # 표면에 없는(active 아님) 도구는 "닳는 중"이 아니다.
    entries = [_skill("alpha"), _skill("beta")]
    report = build_report(
        entries=entries, active_ids={"alpha"}, events=[], now=NOW, window_days=7
    )
    # 창 안 사용 0 → alpha만 active라 닳는 중, beta는 표면 밖이라 제외
    assert report.idle_active == ("alpha",)


def test_outside_pouch_lists_non_catalog_usage() -> None:
    entries = [_skill("alpha")]
    events = [
        _ev("alpha", "2026-07-14T10:00:00"),
        _ev("stranger", "2026-07-14T10:00:00"),
        _ev("stranger", "2026-07-14T11:00:00"),
    ]
    report = build_report(
        entries=entries, active_ids={"alpha"}, events=events, now=NOW, window_days=7
    )
    assert report.outside_pouch == (("stranger", 2),)
    assert report.most_used == (("alpha", 1),)  # 밖의 것은 most_used에 안 섞인다


def test_window_excludes_old_events() -> None:
    entries = [_skill("alpha")]
    events = [_ev("alpha", "2026-06-01T10:00:00")]  # 7일 창 밖
    report = build_report(
        entries=entries, active_ids={"alpha"}, events=events, now=NOW, window_days=7
    )
    assert report.total_uses == 0


def test_render_empty_period_guides_to_widen() -> None:
    report = build_report(entries=[], active_ids=set(), events=[], now=NOW, window_days=7)
    out = "\n".join(render_report_lines(report))
    assert "사용 기록이 없습니다" in out
    assert "--days 30" in out


def test_render_shows_sections() -> None:
    entries = [_skill("alpha"), _skill("beta")]
    events = [_ev("alpha", "2026-07-14T10:00:00"), _ev("stranger", "2026-07-14T10:00:00")]
    report = build_report(
        entries=entries, active_ids={"alpha", "beta"}, events=events, now=NOW, window_days=7
    )
    out = "\n".join(render_report_lines(report))
    assert "많이 쓴 것" in out
    assert "alpha" in out
    assert "닳는 중" in out  # beta
    assert "주머니 밖" in out  # stranger


def test_report_cli_runs(monkeypatch, tmp_path) -> None:
    from typer.testing import CliRunner

    from pouch.cli import app

    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    result = CliRunner().invoke(app, ["report", "--days", "14"])
    assert result.exit_code == 0, result.stdout
    assert "최근 14일" in result.stdout
