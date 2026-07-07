"""백업 코어 — 목적지를 모르는 "싸기/되풀기".

한 디렉토리(`~/.pouch` 등)를 tar.gz 한 덩어리로 싸고, 그걸 다시 되푼다.
어디로 보내느냐는 어댑터의 몫이라, 여기선 source·dest 경로만 다룬다.
now(ISO)는 주입한다 — 코어는 시계를 만들지 않는다(결정적 이름).

담는 방식: source의 *내용물*을 아카이브 루트에 담는다(`memory/…`, `catalog/…`).
그래서 되풀 때 target을 `~/.pouch`로 주면 그 자리에 그대로 복원된다.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

BACKUP_PREFIX = "pouch-backup-"
SNAPSHOT_PREFIX = "pre-restore-"  # 복원 직전 자동 스냅샷 — 백업과 이름으로 구분
_ARCHIVE_SUFFIX = ".tar.gz"


def archive_name(now: str, *, prefix: str = BACKUP_PREFIX) -> str:
    """now(ISO8601)로 파일시스템 안전한 결정적 아카이브 이름을 만든다.

    콜론은 파일명에 부적합(Windows 금지·가독성 저하)이라 하이픈으로 바꾼다.
    예: "2026-07-07T14:30:00" → "pouch-backup-2026-07-07T14-30-00.tar.gz"

    prefix를 갈라 백업(pouch-backup-)과 복원 직전 스냅샷(pre-restore-)이 같은
    초에 실행돼도 파일명이 충돌하지 않게 한다 — 스냅샷이 원본 백업을 덮어쓰면
    "그 덮어쓴 걸 복원"하는 치명적 오염이 생기므로 구조로 막는다."""
    stamp = now.replace(":", "-")
    return f"{prefix}{stamp}{_ARCHIVE_SUFFIX}"


def create_archive(source_dir: Path, dest_path: Path) -> Path:
    """source_dir의 내용물을 dest_path(tar.gz) 한 덩어리로 싼다.

    dest_path는 source_dir 밖이어야 한다(자기 자신을 담는 재귀 회피) — 이 경계는
    어댑터가 보장한다. 반환값은 dest_path(호출부가 이어 쓰기 편하게)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest_path, "w:gz") as tar:
        # arcname="." → source 내용물이 아카이브 루트에 담긴다(경로 이식성).
        tar.add(source_dir, arcname=".")
    return dest_path


def extract_archive(archive_path: Path, target_dir: Path) -> None:
    """아카이브를 target_dir에 되푼다. target_dir이 없으면 만든다."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(target_dir)  # noqa: S202 - 우리가 만든 신뢰된 아카이브
