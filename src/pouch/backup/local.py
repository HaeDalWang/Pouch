"""로컬 어댑터 — 코어를 로컬 폴더에 얹은 백업/복원.

가장 얇은 목적지: "지정 폴더에 아카이브를 놓고/가져온다". 클라우드 인증이
없어 백업↔복원 왕복을 먼저 검증할 수 있다. S3·구글드라이브 어댑터는 이 계약
(now 주입 · 복원 전 스냅샷 · replace 시맨틱)을 그대로 따라 코어 위에 얹는다.

복원(restore)의 두 약속:
- **replace 시맨틱** — 복원은 target을 백업 *시점*으로 되돌린다. 백업 후 생긴
  파일은 사라진다(merge가 아니라 replace라야 "그 시점으로"가 참이 된다).
- **복원의 되돌리기** — 덮기 전에 현재 상태를 스냅샷으로 남긴다. pouch가
  settings.json을 고칠 때 `.bak`을 남기는 것과 같은 정신. 사라진 파일도
  스냅샷 안에 살아있어 소실이 아니다.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pouch.backup.core import (
    SNAPSHOT_PREFIX,
    archive_name,
    create_archive,
    extract_archive,
)


def backup_to_local(source_dir: Path, dest_dir: Path, *, now: str) -> Path:
    """source_dir을 dest_dir 아래 타임스탬프 아카이브로 백업한다. 아카이브 경로 반환."""
    return create_archive(source_dir, dest_dir / archive_name(now))


def _has_content(directory: Path) -> bool:
    """되돌릴 현재 상태가 있는가(디렉토리가 존재하고 비어있지 않은가)."""
    return directory.is_dir() and any(directory.iterdir())


def restore_from_local(
    archive_path: Path,
    target_dir: Path,
    *,
    snapshot_dir: Path,
    now: str,
) -> Path | None:
    """아카이브를 target_dir에 복원한다(replace). 복원 전 현재 상태를 스냅샷.

    현재 상태가 있으면 먼저 스냅샷을 뜬 뒤 target을 비우고 되푼다 — 스냅샷이
    안전판이라, target을 지우고 실패해도 복구 경로가 남는다. 반환값은 스냅샷
    경로(현재 상태가 있었을 때) 또는 None(빈 target — 되돌릴 게 없음).
    """
    snapshot: Path | None = None
    if _has_content(target_dir):
        # 안전판 먼저: 덮기 전 현재 상태를 통째로 보존한다.
        # prefix를 갈라 복원 대상 백업 아카이브와 이름 충돌을 원천 차단한다.
        snapshot_name = archive_name(now, prefix=SNAPSHOT_PREFIX)
        snapshot = create_archive(target_dir, snapshot_dir / snapshot_name)
        # replace 시맨틱: 백업 시점으로 되돌리려면 현재 내용을 먼저 비운다.
        shutil.rmtree(target_dir)

    extract_archive(archive_path, target_dir)
    return snapshot
