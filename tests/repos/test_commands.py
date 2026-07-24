"""`pouch repo` CLI 계약 — 등록/목록/삭제의 사람 말 출력과 종료 코드."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.cli import app

runner = CliRunner()


def _make_origin(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Tester"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        subprocess.run(args, cwd=root, check=True, capture_output=True)
    # 아는 배치 하나(스킬) — 색인이 알아볼 수 있는 모양으로.
    (root / "skills" / "deploy-helper").mkdir(parents=True)
    (root / "skills" / "deploy-helper" / "SKILL.md").write_text(
        "---\nname: deploy-helper\ndescription: deploy tool\n---\n\n# 본문\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=root, check=True, capture_output=True
    )
    return root


@pytest.fixture()
def home(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "pouch-home"))
    return tmp_path


def test_add_then_list_round_trips(home: Path) -> None:
    origin = _make_origin(home / "origin")

    added = runner.invoke(app, ["repo", "add", "team", str(origin)])
    listed = runner.invoke(app, ["repo", "list"])

    assert added.exit_code == 0, added.output
    assert "설치·실행된 것은 없습니다" in added.output  # 등록≠설치를 화면에 못박음
    assert listed.exit_code == 0
    assert "team" in listed.output


def test_empty_list_says_empty_hands_are_normal(home: Path) -> None:
    result = runner.invoke(app, ["repo", "list"])

    assert result.exit_code == 0
    assert "등록된 저장소가 없습니다" in result.output


def test_conflicting_re_add_exits_nonzero(home: Path) -> None:
    origin = _make_origin(home / "origin")
    other = _make_origin(home / "other")
    runner.invoke(app, ["repo", "add", "team", str(origin)])

    result = runner.invoke(app, ["repo", "add", "team", str(other)])

    assert result.exit_code == 1
    # rich가 임의 위치에서 줄을 접으므로 개행을 펴고 확인한다
    assert "다른 주소" in result.output.replace("\n", "")


def test_add_indexes_and_reports_the_count(home: Path) -> None:
    """조각 ② — add가 색인까지 하고 몇 개 알아봤는지 말한다."""
    origin = _make_origin(home / "origin")

    result = runner.invoke(app, ["repo", "add", "team", str(origin)])

    assert result.exit_code == 0, result.output
    assert "색인" in result.output
    assert "1" in result.output  # 스킬 하나를 알아봄


def test_list_shows_indexed_tool_counts(home: Path) -> None:
    origin = _make_origin(home / "origin")
    runner.invoke(app, ["repo", "add", "team", str(origin)])

    result = runner.invoke(app, ["repo", "list"])

    assert "도구 1개" in result.output.replace("\n", "")


def test_remove_also_drops_the_index(home: Path, monkeypatch) -> None:
    """색인은 클론의 파생물 — 등록을 지우면 유령으로 안 남는다."""
    from pouch import paths

    origin = _make_origin(home / "origin")
    runner.invoke(app, ["repo", "add", "team", str(origin)])
    assert (paths.repo_index_root() / "team").exists()

    runner.invoke(app, ["repo", "remove", "team"])

    assert not (paths.repo_index_root() / "team").exists()


def test_search_finds_indexed_tools_with_repo_scoped_names(home: Path) -> None:
    """조각 ③ — 빈손 입구. 검색 결과의 정체에 출처(저장소)가 실려 있다."""
    origin = _make_origin(home / "origin")
    runner.invoke(app, ["repo", "add", "team", str(origin)])

    result = runner.invoke(app, ["repo", "search", "deploy"])

    assert result.exit_code == 0, result.output
    assert "team/deploy-helper" in result.output.replace("\n", "")


def test_search_without_repos_points_to_the_add_door(home: Path) -> None:
    result = runner.invoke(app, ["repo", "search", "anything"])

    assert result.exit_code == 0
    assert "pouch repo add" in result.output.replace("\n", "")


def test_search_miss_is_honest(home: Path) -> None:
    origin = _make_origin(home / "origin")
    runner.invoke(app, ["repo", "add", "team", str(origin)])

    result = runner.invoke(app, ["repo", "search", "zzz-nothing"])

    assert "없습니다" in result.output


def test_remove_round_trips(home: Path) -> None:
    origin = _make_origin(home / "origin")
    runner.invoke(app, ["repo", "add", "team", str(origin)])

    removed = runner.invoke(app, ["repo", "remove", "team"])
    listed = runner.invoke(app, ["repo", "list"])

    assert removed.exit_code == 0
    assert "등록된 저장소가 없습니다" in listed.output
