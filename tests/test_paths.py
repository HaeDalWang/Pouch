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


def test_sources_dir_under_root(monkeypatch) -> None:
    # 소스 스테이징 디렉토리 — 카탈로그의 형제(같은 ~/.pouch 아래, 다른 폴더).
    monkeypatch.delenv("POUCH_HOME", raising=False)
    assert paths.sources_dir().name == "sources"
    assert paths.sources_dir().parent.name == ".pouch"


def test_sources_dir_is_sibling_of_catalog(monkeypatch) -> None:
    # 소스(가리키기)와 카탈로그(진입)는 위치로 갈린다 — 같은 부모, 다른 폴더.
    monkeypatch.delenv("POUCH_HOME", raising=False)
    assert paths.sources_dir().parent == paths.catalog_dir().parent
    assert paths.sources_dir() != paths.catalog_dir()
