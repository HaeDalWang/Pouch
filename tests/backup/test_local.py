"""로컬 어댑터 계약 검증 — 코어를 로컬 폴더에 얹은 백업/복원.

  ① backup_to_local: dest 폴더에 타임스탬프 아카이브를 남긴다
  ② round-trip: 백업 후 원본이 바뀌어도 복원하면 백업 시점으로 돌아온다
  ③ restore 안전장치: 복원 전 현재 상태가 스냅샷으로 보존된다(복원의 되돌리기)
  ④ replace 시맨틱: 백업 후 추가된 파일은 복원으로 사라지고, 스냅샷엔 남는다
  ⑤ 빈 target 복원은 스냅샷 없이 그냥 복원한다(첫 복구 — 되돌릴 현재가 없음)
  ⑥ now는 주입 — 어댑터도 시계를 만들지 않는다
"""

from __future__ import annotations

import tarfile
from pathlib import Path

from pouch.backup.local import backup_to_local, restore_from_local


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_contract1_backup_creates_timestamped_archive(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "note.md", "hi")
    dest = tmp_path / "backups"

    archive = backup_to_local(source, dest, now="2026-07-07T14:30:00")

    assert archive.parent == dest
    assert archive.exists()
    assert "2026-07-07" in archive.name
    assert archive.name.endswith(".tar.gz")


def test_contract2_round_trip_returns_to_backup_moment(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "note.md", "original")
    dest = tmp_path / "backups"
    archive = backup_to_local(source, dest, now="2026-07-07T14:30:00")

    # 백업 후 원본이 변한다
    _write(source / "memory" / "note.md", "changed after backup")

    restore_from_local(archive, source, snapshot_dir=dest, now="2026-07-07T15:00:00")

    assert (source / "memory" / "note.md").read_text(encoding="utf-8") == "original"


def test_contract3_restore_snapshots_current_state_first(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "note.md", "backup-time")
    dest = tmp_path / "backups"
    archive = backup_to_local(source, dest, now="2026-07-07T14:30:00")
    _write(source / "memory" / "note.md", "current-before-restore")

    snapshot = restore_from_local(
        archive, source, snapshot_dir=dest, now="2026-07-07T15:00:00"
    )

    assert snapshot is not None
    assert snapshot.exists()
    # 스냅샷엔 복원 직전(현재) 상태가 들어있다
    with tarfile.open(snapshot, "r:gz") as tar:
        member = tar.extractfile("./memory/note.md")
        assert member is not None
        assert member.read().decode("utf-8") == "current-before-restore"


def test_contract4_replace_semantics_removes_post_backup_files(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "kept.md", "in backup")
    dest = tmp_path / "backups"
    archive = backup_to_local(source, dest, now="2026-07-07T14:30:00")

    # 백업 후 새 파일 추가 — 복원으로 사라져야 한다(백업 시점엔 없었으므로)
    _write(source / "memory" / "added-later.md", "not in backup")

    snapshot = restore_from_local(
        archive, source, snapshot_dir=dest, now="2026-07-07T15:00:00"
    )

    assert (source / "memory" / "kept.md").exists()
    assert not (source / "memory" / "added-later.md").exists()
    # 사라진 파일은 스냅샷에 살아있다(소실 아님)
    assert snapshot is not None
    with tarfile.open(snapshot, "r:gz") as tar:
        names = tar.getnames()
        assert "./memory/added-later.md" in names


def test_contract5_restore_into_empty_target_skips_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "note.md", "data")
    dest = tmp_path / "backups"
    archive = backup_to_local(source, dest, now="2026-07-07T14:30:00")

    empty_target = tmp_path / "fresh"  # 되돌릴 현재가 없음

    snapshot = restore_from_local(
        archive, empty_target, snapshot_dir=dest, now="2026-07-07T15:00:00"
    )

    assert snapshot is None
    assert (empty_target / "memory" / "note.md").read_text(encoding="utf-8") == "data"
