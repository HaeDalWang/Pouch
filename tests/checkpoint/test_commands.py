"""`pouch checkpoint` CLI 통합 검증 — set/show/clear 왕복.

show는 ◆목표 슬롯에 붙일 값이라 목표 문자열만 평문으로 뱉어야 한다(장식 없음).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.checkpoint.commands import app

runner = CliRunner()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    # 앵커 자리가 프로젝트별이 된 뒤로 cwd도 격리해야 한다 — 안 그러면 이 repo를
    # 프로젝트로 잡아 실제 `.pouch/anchor.json`에 쓴다(2026-07-21).
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_set_then_show_returns_goal_only(isolated: Path) -> None:
    result = runner.invoke(app, ["set", "정렬 체크포인트 구현"])
    assert result.exit_code == 0, result.stdout

    shown = runner.invoke(app, ["show"])
    assert shown.exit_code == 0
    # show는 목표 문자열만 — 에이전트가 ◆목표에 그대로 붙일 수 있게 장식 없이
    assert shown.stdout == "정렬 체크포인트 구현"


def test_show_empty_when_no_anchor(isolated: Path) -> None:
    shown = runner.invoke(app, ["show"])
    assert shown.exit_code == 0
    assert shown.stdout == ""


def test_set_overwrites(isolated: Path) -> None:
    runner.invoke(app, ["set", "첫 목표"])
    runner.invoke(app, ["set", "바뀐 목표"])

    shown = runner.invoke(app, ["show"])
    assert shown.stdout == "바뀐 목표"


def test_clear_removes_anchor(isolated: Path) -> None:
    runner.invoke(app, ["set", "목표"])

    cleared = runner.invoke(app, ["clear"])
    assert cleared.exit_code == 0

    shown = runner.invoke(app, ["show"])
    assert shown.stdout == ""
