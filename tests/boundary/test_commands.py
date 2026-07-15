"""`pouch boundary` — 경계 1급 명령(add/list/remove) 검증."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.boundary.commands import app
from pouch.memory.model import (
    SOURCE_USER,
    Direction,
    MemoryEntry,
    MemoryScope,
    MemoryState,
    MemoryType,
)
from pouch.memory.store import MemoryStore

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """글로벌은 POUCH_HOME, 프로젝트는 .git 있는 cwd로 격리."""
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    return tmp_path


def test_add_creates_indexed_user_boundary(workspace: Path) -> None:
    result = runner.invoke(
        app,
        ["add", "-n", "no-force-push", "-d", "force push 금지", "--direction", "deny", "-s", "global"],
    )
    assert result.exit_code == 0, result.stdout

    entry = MemoryStore().get("no-force-push", MemoryScope.GLOBAL)
    assert entry is not None
    assert entry.type is MemoryType.BOUNDARY
    assert entry.direction is Direction.DENY
    assert entry.state is MemoryState.INDEXED
    assert entry.source == SOURCE_USER  # CLI로 건 경계는 언제나 user


def test_add_requires_direction(workspace: Path) -> None:
    # --direction 없으면 실패한다(방향 없는 경계의 애매함을 입구에서 차단).
    result = runner.invoke(app, ["add", "-n", "x", "-d", "요약"])
    assert result.exit_code != 0


def test_list_groups_by_scope_and_shows_direction(workspace: Path) -> None:
    runner.invoke(app, ["add", "-n", "g-deny", "-d", "전역 금지", "--direction", "deny", "-s", "global"])
    runner.invoke(app, ["add", "-n", "p-allow", "-d", "프로젝트 허용", "--direction", "allow", "-s", "project"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.stdout
    assert "global" in result.stdout
    assert "project" in result.stdout
    assert "DENY" in result.stdout
    assert "ALLOW" in result.stdout
    assert "g-deny" in result.stdout
    assert "p-allow" in result.stdout


def test_list_empty_guides(workspace: Path) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "boundary add" in result.stdout


def test_list_hides_archived(workspace: Path) -> None:
    # 강등된(archived) 경계는 더 이상 효력이 없어 목록에서 뺀다.
    store = MemoryStore()
    store.save(
        MemoryEntry(
            name="demoted", description="강등됨", body="",
            type=MemoryType.BOUNDARY, scope=MemoryScope.GLOBAL,
            direction=Direction.ALLOW, state=MemoryState.ARCHIVED,
        )
    )
    result = runner.invoke(app, ["list"])
    assert "demoted" not in result.stdout


def test_remove_deletes_boundary(workspace: Path) -> None:
    runner.invoke(app, ["add", "-n", "temp", "-d", "임시", "--direction", "ask", "-s", "global"])

    result = runner.invoke(app, ["remove", "temp"])
    assert result.exit_code == 0, result.stdout
    assert MemoryStore().get("temp", MemoryScope.GLOBAL) is None


def test_remove_ignores_same_name_non_boundary(workspace: Path) -> None:
    # 같은 이름의 일반 기억은 remove가 건드리지 않는다(경계만 지움).
    store = MemoryStore()
    store.save(
        MemoryEntry(
            name="shared", description="일반 기억", body="본문",
            type=MemoryType.USER, scope=MemoryScope.GLOBAL,
        )
    )
    result = runner.invoke(app, ["remove", "shared"])
    assert result.exit_code != 0  # 경계가 아니라 못 찾음
    assert store.get("shared", MemoryScope.GLOBAL) is not None  # 일반 기억은 살아있음


def test_remove_missing_exits_nonzero(workspace: Path) -> None:
    result = runner.invoke(app, ["remove", "ghost"])
    assert result.exit_code != 0
