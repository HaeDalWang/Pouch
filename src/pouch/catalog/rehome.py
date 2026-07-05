"""rehome — 죽은 upstream 경로를 형제 버전 디렉토리로 재해석한다.

[claude-coupling] 실사용 대상은 Claude 플러그인 캐시(<mkt>/<plugin>/<version>/)
구조다 — 플러그인 업데이트 한 번에 버전 디렉토리가 통째로 사라져 vendored
upstream이 동시에 죽는다. 알고리즘 자체는 경로 패턴을 하드코딩하지 않는다:
"가장 깊은 실존 조상 아래에서 사라진 컴포넌트의 형제 중, 나머지 경로가
실존하는 최신 버전"을 고른다.

주의: 이 모듈은 경로 수준 재해석만 한다. 고른 형제가 정말 같은 도구인지
(스킬만 삭제된 경우 형제 스킬로 하이재킹하지 않는지)는 호출부(sync)가
내용 동일성으로 검증해야 한다.
"""

from __future__ import annotations

from pathlib import Path


def rehome_upstream(upstream: str) -> Path | None:
    """죽은 경로를 형제 버전으로 재해석한다. 후보가 없으면 None.

    파일시스템을 읽지만 절대 쓰지 않는다 — 판단·기록은 호출부의 몫.
    """
    dead = Path(upstream)
    anchor, missing_index = _deepest_existing(dead)
    if anchor is None:
        return None

    rest = Path(*dead.parts[missing_index + 1 :]) if missing_index + 1 < len(dead.parts) else None
    candidates: list[tuple[str, Path]] = []
    for sibling in anchor.iterdir():
        if not sibling.is_dir() or sibling.name.startswith("."):
            continue
        target = sibling / rest if rest else sibling
        if target.exists():
            candidates.append((sibling.name, target))

    if not candidates:
        return None
    return max(candidates, key=lambda c: _version_key(c[0]))[1]


def _deepest_existing(path: Path) -> tuple[Path | None, int]:
    """가장 깊은 실존 조상과, 그 바로 아래 사라진 컴포넌트의 인덱스.

    경로 전체가 실존하면 (None, -1) — 재해석할 것이 없다.
    """
    current = Path(path.parts[0])
    for index, part in enumerate(path.parts[1:], start=1):
        step = current / part
        if not step.exists():
            return current, index
        current = step
    return None, -1


def _version_key(name: str) -> tuple:
    """버전 정렬 키. pre-release(-rc 등)는 같은 release의 정식판보다 낮다."""
    release, _, pre = name.partition("-")
    release_key = tuple(_chunk_key(c) for c in release.split("."))
    pre_key = tuple(_chunk_key(c) for c in pre.split(".")) if pre else ()
    return (release_key, 0 if pre else 1, pre_key)


def _chunk_key(chunk: str) -> tuple[int, int | str]:
    """숫자는 수치로, 문자는 문자로 — 혼합 비교 TypeError 없이 정렬한다."""
    return (0, int(chunk)) if chunk.isdigit() else (1, chunk)
