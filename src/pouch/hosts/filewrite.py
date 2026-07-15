"""파일 호스트 스냅샷 기록 — 기존 파일이 있으면 백업하고 덮어쓴다.

hooks/settings.py의 write_settings와 같은 정신(되돌릴 수 있게 .bak 남김)이되,
JSON이 아니라 임의 텍스트(steering 마크다운 등)를 쓴다. 파일 호스트 어댑터들이 공유.
"""

from __future__ import annotations

from pathlib import Path


def write_snapshot(path: Path, content: str) -> Path | None:
    """텍스트 스냅샷을 기록한다. 기존 파일이 있었으면 백업하고 그 경로를 반환한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if path.exists():
        backup = path.with_name(path.name + ".bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(content, encoding="utf-8")
    return backup
