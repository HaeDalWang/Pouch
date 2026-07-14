"""`pouch catalog migrate` CLI 계약 — 관문 이전 잉여(194)를 소스로 되돌리는 일회성 통로.

두 정책이 배선에 박힌다:
  일회성 — reconcile는 매 evolve마다 자동으로 돌지만 migrate는 파괴적(카탈로그
           삭제)이라 자동 루프에 없다. 사용자가 의도적으로 부르는 backfill.
  백업 동반 — 실데이터를 옮기므로 적용 전 자동 백업(restore의 사전 스냅샷과 같은 정신).

dry-run은 읽기전용이라 백업도 이동도 안 한다(볼게, 해 아님). --yes/대화형 동의 시에만
백업 후 강등한다.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pouch import paths
from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.cli import app

runner = CliRunner()


def _catalog() -> CatalogStore:
    return CatalogStore(catalog_dir=paths.catalog_dir())


def _sources() -> CatalogStore:
    return CatalogStore(catalog_dir=paths.sources_dir())


def _skill(entry_id: str, *, kind: ToolKind = ToolKind.SKILL) -> ToolEntry:
    return ToolEntry.linked(
        id=entry_id, kind=kind, source="ecc",
        title=entry_id, description="d", recipe={}, surface="plugin",
    )


def test_dry_run_lists_without_moving_or_backup() -> None:
    # Arrange — 안 쓴 스킬이 카탈로그에 있다(빈 usage → 안 씀).
    _catalog().save(_skill("unused"))

    # Act — dry-run.
    result = runner.invoke(app, ["catalog", "migrate", "--dry-run"])

    # Assert — 목록엔 뜨지만 아무것도 안 옮기고, 백업도 안 뜬다.
    assert result.exit_code == 0
    assert "unused" in result.stdout
    assert _catalog().get("unused") is not None  # 카탈로그 잔류
    assert list(_sources().list()) == []  # 소스 비어있음
    assert list(paths.backup_dir().glob("pouch-backup-*.tar.gz")) == []  # 백업 안 함(읽기전용)


def test_yes_backs_up_then_demotes() -> None:
    # Arrange
    _catalog().save(_skill("unused"))

    # Act — 확인 건너뛰고 적용.
    result = runner.invoke(app, ["catalog", "migrate", "--yes"])

    # Assert — 강등됐고, 적용 전 백업이 남았다.
    assert result.exit_code == 0
    assert _catalog().get("unused") is None  # 카탈로그에서 내려감
    assert _sources().get("unused") is not None  # 소스로 이동
    backups = list(paths.backup_dir().glob("pouch-backup-*.tar.gz"))
    assert len(backups) == 1  # 이동 전 자동 백업 동반


def test_nothing_to_migrate_is_friendly_and_no_backup() -> None:
    # Arrange — 실제로 쓴 도구만 있다(강등 대상 없음).
    from pouch.evolution.usage_log import UsageEvent, append_event

    _catalog().save(_skill("used"))
    append_event(UsageEvent("used", "2026-07-13T09:00:00"), log_path=paths.usage_log_path())

    # Act
    result = runner.invoke(app, ["catalog", "migrate", "--yes"])

    # Assert — 강등 없음, 백업도 안 뜬다(옮길 게 없는데 백업만 쌓이지 않게).
    assert result.exit_code == 0
    assert _catalog().get("used") is not None
    assert list(paths.backup_dir().glob("pouch-backup-*.tar.gz")) == []


def test_declining_confirmation_moves_nothing() -> None:
    # Arrange
    _catalog().save(_skill("unused"))

    # Act — 대화형 확인에 'n'(거부).
    result = runner.invoke(app, ["catalog", "migrate"], input="n\n")

    # Assert — 그대로 둔다(파괴적이라 기본 no).
    assert result.exit_code == 0
    assert _catalog().get("unused") is not None
    assert list(paths.backup_dir().glob("pouch-backup-*.tar.gz")) == []


def test_non_signal_kinds_not_listed() -> None:
    # Arrange — 훅은 신호가 안 찍혀 "안 씀"으로 보이지만 강등 대상 아니다.
    _catalog().save(_skill("some-hook", kind=ToolKind.HOOK))

    # Act
    result = runner.invoke(app, ["catalog", "migrate", "--dry-run"])

    # Assert — 목록에 안 뜬다(신호 없음 ≠ 안 쓰임).
    assert result.exit_code == 0
    assert "some-hook" not in result.stdout
    assert _catalog().get("some-hook") is not None
