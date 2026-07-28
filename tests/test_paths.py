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


def test_find_project_root_excludes_home(tmp_path: Path, monkeypatch) -> None:
    # 홈에 .pouch가 있어도(전역 루트가 ~/.pouch다) 홈을 프로젝트로 치지 않는다.
    # 그러지 않으면 .git 없는 폴더에서 일할 때 프로젝트 로그 경로가 전역과 겹쳐
    # 사용 이벤트가 이중 기록된다(관측된 버그).
    home = tmp_path / "home"
    (home / ".pouch").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    work = home / "salt" / "proj"  # .git 없는 작업 폴더
    work.mkdir(parents=True)

    assert paths.find_project_root(work) is None


def test_find_project_root_home_itself_is_none(tmp_path: Path, monkeypatch) -> None:
    # 홈 디렉토리 자체를 start로 줘도 프로젝트가 아니다.
    home = tmp_path / "home"
    (home / ".pouch").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    assert paths.find_project_root(home) is None


def test_find_project_root_detects_real_project_under_home(
    tmp_path: Path, monkeypatch
) -> None:
    # 홈 제외는 홈 '아래'의 진짜 프로젝트(.git)까지 막으면 안 된다.
    home = tmp_path / "home"
    (home / ".pouch").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    proj = home / "work" / "repo"
    (proj / ".git").mkdir(parents=True)

    assert paths.find_project_root(proj / "src") == proj


def test_project_usage_log_path_none_under_home_without_git(
    tmp_path: Path, monkeypatch
) -> None:
    # 홈 오인이 사라지면 .git 없는 폴더의 프로젝트 로그는 없다 — 전역과 겹치지 않는다.
    home = tmp_path / "home"
    (home / ".pouch").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    work = home / "salt" / "ezl"
    work.mkdir(parents=True)

    assert paths.project_usage_log_path(work) is None


def test_project_memory_dir_under_root(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".git").mkdir()

    # Act / Assert
    assert paths.project_memory_dir(tmp_path) == tmp_path / ".pouch" / "memory"


def test_project_anchor_path_under_root(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".git").mkdir()

    # Act / Assert
    assert paths.project_anchor_path(tmp_path) == tmp_path / ".pouch" / "anchor.json"


def test_project_anchor_path_none_outside_project(tmp_path: Path) -> None:
    # 프로젝트 표식이 없으면 프로젝트 앵커 자리도 없다.
    assert paths.project_anchor_path(tmp_path) is None


def test_resolve_anchor_path_prefers_project(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".git").mkdir()

    # Act / Assert — 프로젝트 안이면 글로벌로 새지 않는다(오염 방지의 핵심).
    assert paths.resolve_anchor_path(tmp_path) == tmp_path / ".pouch" / "anchor.json"


def test_resolve_anchor_path_falls_back_to_global(tmp_path: Path, monkeypatch) -> None:
    # Arrange — 프로젝트 밖에서 박은 목표는 글로벌 칸에 산다.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "home"))

    # Act / Assert
    assert paths.resolve_anchor_path(tmp_path) == paths.anchor_path()


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
