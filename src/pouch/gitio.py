"""git shell-out 공용 헬퍼 — 세트 레지스트리와 도구 저장소가 같이 쓴다.

원래 sets/registry.py 안에 살았는데 Phase 4.8(저장소 모델)이 똑같은 일(clone·
pull·remote 조회)을 하게 되면서 한 곳으로 뽑았다. shell-out인 이유(원 설계 그대로):
사용자의 기존 git 인증(SSH/HTTPS)을 그대로 물려받고, 파이썬 git 라이브러리
의존성을 안 늘린다. 매체가 git이라 버전·이력·되돌리기가 공짜다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_TIMEOUT = 120  # clone/pull은 네트워크라 넉넉히


class GitError(Exception):
    """git 조작 실패 — 호출부(CLI)가 사람 말로 옮겨 exit."""


def run_git(args: list[str], *, cwd: Path | None = None) -> str:
    """git을 shell-out한다. 실패는 GitError로 옮긴다(멈춤 방지 타임아웃)."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise GitError("git이 설치돼 있지 않습니다.") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git 실행 실패: {exc}") from exc
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {args[0]} 실패")
    return result.stdout.strip()


def clone_url_of(clone_dir: Path) -> str | None:
    """클론의 origin 원격 URL. 클론이 아니면 None."""
    if not (clone_dir / ".git").exists():
        return None
    try:
        return run_git(["remote", "get-url", "origin"], cwd=clone_dir)
    except GitError:
        return None
