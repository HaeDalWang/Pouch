"""레지스트리 — git 기반 세트 공유 매체(받는 쪽).

raft의 첫 문. 팀 공유 레지스트리 repo를 `~/.pouch/registry/`에 clone하고, 재-pull은
`git pull`로 멱등 갱신한다. 당겨온 세트는 별도 티어라 내가 만든 `~/.pouch/sets/`와
안 섞이고, 이름 충돌 시 로컬(내 것)이 이긴다(개인 우선 — sets/model.available_sets).

git은 shell-out한다(`status.py`의 `_git_revision`과 같은 패턴): 사용자의 기존 git
인증(SSH/HTTPS)을 그대로 물려받고, 파이썬 git 라이브러리 의존성을 안 늘린다. 매체가
git이라 버전·이력·되돌리기가 공짜다. 설계: docs/RAFT-DESIGN.md.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_TIMEOUT = 120  # clone/pull은 네트워크라 넉넉히(status의 2초와 다른 성격)


class RegistryError(Exception):
    """레지스트리 조작 실패 — 호출부(CLI)가 사람 말로 옮겨 exit."""


def _git(args: list[str], *, cwd: Path | None = None) -> str:
    """git을 shell-out한다. 실패는 RegistryError로 옮긴다(멈춤 방지 타임아웃)."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise RegistryError("git이 설치돼 있지 않습니다.") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise RegistryError(f"git 실행 실패: {exc}") from exc
    if result.returncode != 0:
        raise RegistryError(result.stderr.strip() or f"git {args[0]} 실패")
    return result.stdout.strip()


def remote_url(registry_dir: Path) -> str | None:
    """레지스트리의 origin 원격 URL. 클론 전이면 None."""
    if not (registry_dir / ".git").exists():
        return None
    try:
        return _git(["remote", "get-url", "origin"], cwd=registry_dir)
    except RegistryError:
        return None


def pull_registry(registry_dir: Path, *, url: str | None = None) -> str:
    """레지스트리를 clone(첫 회)하거나 pull(갱신)한다. 반환: 실제 origin URL.

    - url 있고 클론 전 → clone.
    - url 있고 이미 있음 → 같은 원격이면 pull, 다르면 거부(조용한 덮어쓰기 금지).
    - url 없음 → 기존 pull(레지스트리 없으면 안내 에러).
    """
    has_clone = (registry_dir / ".git").exists()

    if url:
        if has_clone:
            existing = remote_url(registry_dir)
            if existing != url:
                raise RegistryError(
                    f"이미 다른 레지스트리가 있습니다({existing}). "
                    f"바꾸려면 {registry_dir}를 지우고 다시 pull 하세요."
                )
            _git(["pull", "--ff-only"], cwd=registry_dir)
        else:
            registry_dir.parent.mkdir(parents=True, exist_ok=True)
            _git(["clone", url, str(registry_dir)])
        return url

    if not has_clone:
        raise RegistryError(
            "레지스트리가 없습니다. 처음엔 URL을 주세요: pouch set pull <git-url>"
        )
    _git(["pull", "--ff-only"], cwd=registry_dir)
    return remote_url(registry_dir) or ""
