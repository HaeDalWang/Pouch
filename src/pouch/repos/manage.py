"""도구 저장소 등록 — Phase 4.8 조각 ①. helm repo add/list/remove의 pouch판.

모델 락(배승도, 2026-07-24): 주소를 등록하는 행위가 곧 신뢰 표명이다(helm처럼
퍼블릭 주소여도 됨). chart = 낱개 도구 — 저장소 안에 스킬·MCP 들이 산다.
기본 저장소는 없다: helm repo list처럼 빈손으로 시작하고 주소는 사람이 전한다.

설계 원칙 둘:

- **장부 파일이 없다.** 등록 상태 = `~/.pouch/repos/<이름>/` 클론 디렉토리 자체,
  주소 = 그 클론의 git remote. 별도 목록 파일을 두면 실제 디렉토리와 어긋난
  사본이 생긴다(단일 진실).
- **등록까지만.** 여기서는 아무것도 읽거나 추천하지 않는다 — 색인(조각 ②)·추천
  합류(조각 ③)·설치(조각 ④)는 다음 조각. 등록은 카탈로그·표면을 안 건드린다.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from pouch.gitio import GitError, clone_url_of, run_git


class RepoError(Exception):
    """저장소 조작 실패 — 호출부(CLI)가 사람 말로 옮겨 exit."""


# 이름이 곧 폴더 이름이다 — 경로 탈출(`../`·`/`)과 이상 문자를 입구에서 막는다.
# 영숫자로 시작, 이후 영숫자·`.`·`_`·`-`만. 구분자가 없으니 `..`도 폴더를 못 넘는다.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class RepoInfo:
    """등록된 저장소 하나 — 이름(폴더)과 주소(git remote에서 읽음)."""

    name: str
    url: str | None
    path: Path


def _require_safe_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise RepoError(
            f"'{name}'은 저장소 이름으로 못 씁니다 — 영숫자로 시작하고 "
            "영숫자·점·밑줄·대시만 쓸 수 있습니다(폴더 이름이 되기 때문)."
        )


def _canonical_url(url: str) -> str:
    """로컬 경로 주소는 절대경로로 편다(원격 URL은 그대로).

    git이 remote에 적어두는 로컬 경로는 절대경로 꼴이라, 사용자가 준 상대경로
    (`./origin`)와 문자열로 비교하면 같은 주소를 다르다고 오판한다 — 멱등 재등록이
    깨지는 실측 버그. 등록·비교 모두 이 canonical 형으로 통일한다.
    """
    path = Path(url).expanduser()
    if path.exists():
        return str(path.resolve())
    return url


def add_repo(name: str, url: str, *, repos_dir: Path) -> RepoInfo:
    """주소를 이름으로 등록한다(clone). 재등록은 갱신(pull, 멱등).

    같은 이름을 다른 주소로 다시 등록하려 하면 거부한다 — 조용한 덮어쓰기 금지
    (세트 레지스트리와 같은 정신). 바꾸려면 remove 후 add.
    """
    _require_safe_name(name)
    target = repos_dir / name
    wanted = _canonical_url(url)

    try:
        if (target / ".git").exists():
            existing = clone_url_of(target)
            if existing is None or _canonical_url(existing) != wanted:
                raise RepoError(
                    f"'{name}'은 이미 다른 주소({existing})로 등록돼 있습니다. "
                    f"바꾸려면 먼저 pouch repo remove {name} 하세요."
                )
            run_git(["pull", "--ff-only"], cwd=target)
        else:
            repos_dir.mkdir(parents=True, exist_ok=True)
            run_git(["clone", wanted, str(target)])
    except GitError as exc:
        raise RepoError(str(exc)) from exc

    return RepoInfo(name=name, url=wanted, path=target)


def list_repos(*, repos_dir: Path) -> list[RepoInfo]:
    """등록된 저장소 목록(이름순, 결정적). 클론이 아닌 잡폴더는 세지 않는다."""
    if not repos_dir.exists():
        return []
    found = [
        RepoInfo(name=child.name, url=clone_url_of(child), path=child)
        for child in sorted(repos_dir.iterdir())
        if (child / ".git").exists()
    ]
    return found


def remove_repo(name: str, *, repos_dir: Path) -> bool:
    """등록을 지운다(클론 삭제). 없었으면 False(멱등).

    지워지는 건 바깥 데이터의 사본뿐이다 — 개인화(카탈로그 overlay·기억)는 여기
    산 적이 없어 "떨어진다 ≠ 삭제된다"와 부딪히지 않는다. 되돌리기는 add 한 번.
    """
    _require_safe_name(name)
    target = repos_dir / name
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True
