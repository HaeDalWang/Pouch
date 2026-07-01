"""프로젝트 루트/메모리 경로 탐지 검증."""

from __future__ import annotations

from pathlib import Path

from pouch import paths


def test_find_project_root_detects_git_dir(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    # Act
    root = paths.find_project_root(nested)

    # Assert
    assert root == tmp_path


def test_find_project_root_detects_pouch_dir(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".pouch").mkdir()

    # Act / Assert
    assert paths.find_project_root(tmp_path) == tmp_path


def test_find_project_root_returns_none_without_markers(tmp_path: Path) -> None:
    # Act / Assert
    assert paths.find_project_root(tmp_path) is None


def test_project_memory_dir_under_root(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".git").mkdir()

    # Act / Assert
    assert paths.project_memory_dir(tmp_path) == tmp_path / ".pouch" / "memory"


def test_global_memory_dir_under_home(monkeypatch) -> None:
    # 오버라이드를 걷어내고 '기본값'(~/.pouch)을 검증한다.
    monkeypatch.delenv("POUCH_HOME", raising=False)
    assert paths.global_memory_dir().name == "memory"
    assert paths.global_memory_dir().parent.name == ".pouch"
