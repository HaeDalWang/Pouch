"""레지스트리 — git 기반 세트 공유 매체(받는 쪽).

raft의 첫 문. 팀 공유 레지스트리 repo를 `~/.pouch/registry/`에 clone하고, 재-pull은
`git pull`로 멱등 갱신한다. 당겨온 세트는 별도 티어라 내가 만든 `~/.pouch/sets/`와
안 섞이고, 이름 충돌 시 로컬(내 것)이 이긴다(개인 우선 — sets/model.available_sets).

git shell-out 헬퍼는 gitio로 뽑혀 나갔다(Phase 4.8 저장소 모델과 공용) — 인증
승계·의존성 0 이유는 그쪽 문서 참조. 설계: docs/RAFT-DESIGN.md.
"""

from __future__ import annotations

from pathlib import Path

from pouch.gitio import GitError, clone_url_of, run_git

# 기존 호출부·테스트가 아는 이름 유지 — 같은 실패 종류의 별칭이다.
RegistryError = GitError


def remote_url(registry_dir: Path) -> str | None:
    """레지스트리의 origin 원격 URL. 클론 전이면 None."""
    return clone_url_of(registry_dir)


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
            run_git(["pull", "--ff-only"], cwd=registry_dir)
        else:
            registry_dir.parent.mkdir(parents=True, exist_ok=True)
            run_git(["clone", url, str(registry_dir)])
        return url

    if not has_clone:
        raise RegistryError(
            "레지스트리가 없습니다. 처음엔 URL을 주세요: pouch set pull <git-url>"
        )
    run_git(["pull", "--ff-only"], cwd=registry_dir)
    return remote_url(registry_dir) or ""
