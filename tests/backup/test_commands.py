"""`pouch backup` / `pouch restore` CLI 배선 검증 — 실제 명령 왕복.

conftest가 POUCH_HOME을 tmp로 격리한다. POUCH_BACKUP_DIR도 tmp로 돌려
실제 홈 형제 폴더를 건드리지 않는다.

  ① backup: 전역 주머니를 아카이브로 싸고 경로를 안내한다
  ② 빈 주머니 백업은 안내만 하고 아카이브를 안 만든다
  ③ restore --yes: 백업 시점으로 되돌리고, 현재 상태를 스냅샷으로 남긴다
  ④ 없는 아카이브 restore는 코드 1로 실패한다
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch import paths
from pouch.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _backup_dir(tmp_path_factory, monkeypatch) -> None:
    monkeypatch.setenv("POUCH_BACKUP_DIR", str(tmp_path_factory.mktemp("backups")))


def _seed_pouch(text: str) -> Path:
    """전역 주머니에 파일 하나를 심는다(POUCH_HOME은 conftest가 격리)."""
    note = paths.global_memory_dir() / "note.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text, encoding="utf-8")
    return note


def test_backup_creates_archive_in_backup_dir() -> None:
    _seed_pouch("role: devops")

    result = runner.invoke(app, ["backup"])

    assert result.exit_code == 0
    assert "백업 완료" in result.stdout
    archives = list(paths.backup_dir().glob("pouch-backup-*.tar.gz"))
    assert len(archives) == 1


def test_backup_empty_pouch_creates_nothing() -> None:
    result = runner.invoke(app, ["backup"])

    assert result.exit_code == 0
    assert "백업할 주머니가 아직 없습니다" in result.stdout
    assert not paths.backup_dir().exists() or not list(paths.backup_dir().glob("*.tar.gz"))


def test_restore_returns_to_backup_moment_and_snapshots() -> None:
    note = _seed_pouch("original")
    runner.invoke(app, ["backup"])
    archive = next(paths.backup_dir().glob("pouch-backup-*.tar.gz"))
    note.write_text("changed after backup", encoding="utf-8")

    result = runner.invoke(app, ["restore", str(archive), "--yes"])

    assert result.exit_code == 0
    assert note.read_text(encoding="utf-8") == "original"
    assert "복원 직전 스냅샷" in result.stdout
    # 백업 아카이브와 복원 직전 스냅샷은 이름으로 구분된다(충돌 방지)
    assert len(list(paths.backup_dir().glob("pouch-backup-*.tar.gz"))) == 1
    assert len(list(paths.backup_dir().glob("pre-restore-*.tar.gz"))) == 1


def test_restore_missing_archive_fails() -> None:
    result = runner.invoke(app, ["restore", "/nope/missing.tar.gz", "--yes"])

    assert result.exit_code == 1
    assert "찾을 수 없습니다" in result.stdout
