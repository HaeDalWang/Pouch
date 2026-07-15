"""맥락 개인화 레인 2a(P3) — 프로젝트 로컬 사용 로그 이중 기록 + 경로."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch import paths
from pouch.evolution.commands import app
from pouch.evolution.usage_log import read_events

runner = CliRunner()


def test_project_usage_log_path_in_and_out_of_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    assert paths.project_usage_log_path() == project / ".pouch" / "usage.jsonl"

    outside = tmp_path / "nowhere"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert paths.project_usage_log_path() is None  # 프로젝트 밖이면 None


def test_log_dual_writes_global_and_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)

    payload = json.dumps({"tool_name": "Skill", "tool_input": {"skill": "alpha"}})
    result = runner.invoke(app, ["log"], input=payload)
    assert result.exit_code == 0

    # 전역과 프로젝트 로컬 양쪽에 같은 이벤트가 남는다.
    global_events = read_events(log_path=paths.usage_log_path())
    project_events = read_events(log_path=project / ".pouch" / "usage.jsonl")
    assert [e.entry_id for e in global_events] == ["alpha"]
    assert [e.entry_id for e in project_events] == ["alpha"]


def test_log_outside_project_writes_global_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    outside = tmp_path / "nowhere"
    outside.mkdir()
    monkeypatch.chdir(outside)

    payload = json.dumps({"tool_name": "Skill", "tool_input": {"skill": "alpha"}})
    result = runner.invoke(app, ["log"], input=payload)
    assert result.exit_code == 0

    assert [e.entry_id for e in read_events(log_path=paths.usage_log_path())] == ["alpha"]
    # 프로젝트 밖이라 로컬 사이드카는 안 생긴다.
    assert paths.project_usage_log_path() is None
