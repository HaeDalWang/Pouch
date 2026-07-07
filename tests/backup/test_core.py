"""백업 코어 계약 검증 — 목적지를 모르는 순수 "싸기/되풀기".

  ① archive_name: now(ISO)로 파일시스템 안전한 결정적 이름을 만든다(콜론 없음)
  ② create_archive: source 디렉토리의 내용을 한 아카이브 파일로 싼다
  ③ round-trip: 싼 것을 딴 곳에 되풀면 원본과 동일한 트리 + 내용
  ④ 빈 source도 안전하다(첫 백업 — 아직 아무것도 없음)
  ⑤ extract는 target 디렉토리가 없으면 만든다
  ⑥ 시계는 주입 — 코어는 now를 만들지 않는다(결정적)
"""

from __future__ import annotations

from pathlib import Path

from pouch.backup.core import archive_name, create_archive, extract_archive


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_contract1_archive_name_is_deterministic_and_fs_safe() -> None:
    name = archive_name("2026-07-07T14:30:00")

    # 결정적: 같은 now면 같은 이름
    assert name == archive_name("2026-07-07T14:30:00")
    # 파일시스템 안전: 콜론 없음(Windows·가독성), tar.gz 확장자
    assert ":" not in name
    assert name.endswith(".tar.gz")
    # 언제 것인지 사람이 읽을 수 있다
    assert "2026-07-07" in name


def test_contract2_create_archive_packs_source_contents(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "user-role.md", "role: devops")
    _write(source / "catalog" / "aws-iam.md", "id: aws-iam")
    dest = tmp_path / "backup.tar.gz"

    result = create_archive(source, dest)

    assert result == dest
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_contract3_round_trip_restores_identical_tree(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "user-role.md", "role: devops")
    _write(source / "catalog" / "aws-iam.md", "id: aws-iam")
    _write(source / "usage.jsonl", '{"entry_id": "aws-iam", "ts": "2026-07-01T10:00:00"}')
    dest = tmp_path / "backup.tar.gz"
    create_archive(source, dest)

    target = tmp_path / "restored"
    extract_archive(dest, target)

    assert (target / "memory" / "user-role.md").read_text(encoding="utf-8") == "role: devops"
    assert (target / "catalog" / "aws-iam.md").read_text(encoding="utf-8") == "id: aws-iam"
    assert "aws-iam" in (target / "usage.jsonl").read_text(encoding="utf-8")


def test_contract4_empty_source_is_safe(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    source.mkdir()
    dest = tmp_path / "backup.tar.gz"

    create_archive(source, dest)
    target = tmp_path / "restored"
    extract_archive(dest, target)

    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_contract5_extract_creates_missing_target(tmp_path: Path) -> None:
    source = tmp_path / "pouch"
    _write(source / "memory" / "note.md", "hi")
    dest = tmp_path / "backup.tar.gz"
    create_archive(source, dest)

    target = tmp_path / "deep" / "not" / "there"  # 아직 없음
    extract_archive(dest, target)

    assert (target / "memory" / "note.md").read_text(encoding="utf-8") == "hi"
