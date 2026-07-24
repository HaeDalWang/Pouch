"""저장소 등록 — Phase 4.8 조각 ①. helm repo add/list/remove의 pouch판.

배승도 락(2026-07-24): "helmchart을 다운받기 위해서는 helm repository주소가
필요하고 그건 솔직히 말해서 그냥 퍼블릭이잔아?? 그리고 그 주소안에 차트들이
잇는거고 그것처럼 하겟다 이거지"

sets/test_registry.py처럼 실제 로컬 git repo를 원격 삼아 왕복 검증한다
(네트워크 없이 file 경로 clone). 핵심 계약:
  - 여러 저장소를 이름으로 등록 (registry가 하나뿐이던 제약의 일반화)
  - 같은 이름+같은 주소 재등록 = 갱신(pull, 멱등) / 다른 주소 = 거부
  - 장부 파일 없음 — 클론 디렉토리와 git remote가 유일한 진실
  - 이름은 파일시스템 안전(경로 탈출 불가)해야 등록된다
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pouch.repos.manage import RepoError, add_repo, list_repos, remove_repo


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _make_origin(root: Path, filename: str = "SKILL.md") -> Path:
    """도구 파일 하나를 담은 git repo를 만든다 — 등록할 '주소' 역할."""
    root.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "Tester"], root)
    _run(["git", "config", "commit.gpgsign", "false"], root)
    (root / filename).write_text("# 도구\n", encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "init"], root)
    return root


@pytest.fixture()
def origin(tmp_path: Path) -> Path:
    return _make_origin(tmp_path / "origin")


@pytest.fixture()
def repos_dir(tmp_path: Path) -> Path:
    return tmp_path / "repos"


def test_add_clones_the_address(origin: Path, repos_dir: Path) -> None:
    info = add_repo("team", str(origin), repos_dir=repos_dir)

    assert info.name == "team"
    assert info.url == str(origin)
    assert (repos_dir / "team" / ".git").exists()


def test_re_add_with_same_address_pulls_new_content(origin: Path, repos_dir: Path) -> None:
    """재등록 = 갱신 — helm repo add를 다시 쳐도 에러가 아니듯 멱등이다."""
    add_repo("team", str(origin), repos_dir=repos_dir)
    (origin / "new-tool.md").write_text("# 새 도구\n", encoding="utf-8")
    _run(["git", "add", "-A"], origin)
    _run(["git", "commit", "-q", "-m", "add tool"], origin)

    add_repo("team", str(origin), repos_dir=repos_dir)

    assert (repos_dir / "team" / "new-tool.md").exists()


def test_re_add_with_a_relative_path_is_still_idempotent(
    origin: Path, repos_dir: Path, monkeypatch
) -> None:
    """상대경로 주소 회귀 방어 — git은 remote에 절대경로를 적어두므로, 문자열
    그대로 비교하면 같은 주소를 다르다고 오판해 멱등 재등록이 깨진다(실측)."""
    monkeypatch.chdir(origin.parent)

    add_repo("team", "./origin", repos_dir=repos_dir)
    add_repo("team", "./origin", repos_dir=repos_dir)  # 거부되면 여기서 터진다

    repos = list_repos(repos_dir=repos_dir)
    assert repos[0].name == "team"


def test_re_add_with_a_different_address_is_refused(
    origin: Path, repos_dir: Path, tmp_path: Path
) -> None:
    """같은 이름을 조용히 다른 주소로 덮지 않는다(registry와 같은 정신)."""
    other = _make_origin(tmp_path / "other")
    add_repo("team", str(origin), repos_dir=repos_dir)

    with pytest.raises(RepoError, match="다른 주소"):
        add_repo("team", str(other), repos_dir=repos_dir)


def test_two_repos_live_side_by_side(origin: Path, repos_dir: Path, tmp_path: Path) -> None:
    """여러 저장소 등록 — registry가 하나뿐이던 제약을 일반화한 핵심."""
    other = _make_origin(tmp_path / "other")

    add_repo("team", str(origin), repos_dir=repos_dir)
    add_repo("public", str(other), repos_dir=repos_dir)

    names = [r.name for r in list_repos(repos_dir=repos_dir)]
    assert names == ["public", "team"]  # 이름순(결정적)


def test_list_reads_urls_from_git_itself(origin: Path, repos_dir: Path) -> None:
    """장부 파일이 따로 없다 — 클론의 git remote가 유일한 진실(어긋날 사본 없음)."""
    add_repo("team", str(origin), repos_dir=repos_dir)

    repos = list_repos(repos_dir=repos_dir)

    assert repos[0].url == str(origin)


def test_list_is_empty_before_any_add(repos_dir: Path) -> None:
    """helm repo list처럼 처음엔 빈손 — 기본 저장소를 물려두지 않는다(락)."""
    assert list_repos(repos_dir=repos_dir) == []


def test_a_stray_non_git_folder_is_not_a_repo(repos_dir: Path) -> None:
    """클론이 아닌 잡폴더가 끼어 있어도 목록이 거짓말하지 않는다."""
    (repos_dir / "junk").mkdir(parents=True)

    assert list_repos(repos_dir=repos_dir) == []


def test_remove_deletes_the_clone(origin: Path, repos_dir: Path) -> None:
    add_repo("team", str(origin), repos_dir=repos_dir)

    assert remove_repo("team", repos_dir=repos_dir) is True
    assert not (repos_dir / "team").exists()


def test_remove_of_a_missing_repo_is_quiet(repos_dir: Path) -> None:
    """멱등 — 없는 걸 지워도 안 죽는다."""
    assert remove_repo("ghost", repos_dir=repos_dir) is False


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", ".hidden", "한글이름", "a b"])
def test_unsafe_names_are_refused(bad: str, origin: Path, repos_dir: Path) -> None:
    """이름이 곧 폴더 이름이라 경로 탈출·이상 문자를 입구에서 막는다."""
    with pytest.raises(RepoError, match="이름"):
        add_repo(bad, str(origin), repos_dir=repos_dir)


def test_remove_refuses_unsafe_names_too(repos_dir: Path) -> None:
    """remove도 같은 관문 — add만 막으면 remove가 탈출구가 된다."""
    with pytest.raises(RepoError, match="이름"):
        remove_repo("../escape", repos_dir=repos_dir)
