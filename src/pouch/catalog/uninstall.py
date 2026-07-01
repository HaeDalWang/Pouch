"""uninstall/reattach — install.py의 거울상. "떨어진다 ≠ 삭제된다".

핵심 계약: **이 모듈은 카탈로그를 절대 만지지 않는다.** 활성 표면(SKILL.md /
mcpServers)만 걷어낸다. 엔트리+overlay는 store에 그대로 남고, 재부착은
install.install_entry 재실행이다. drop이 overlay를 만질 경로가 구조상 없다 —
overlay는 "살려두는" 게 아니라 죽을 자리에 애초에 없다.

install.py와 같은 결: 순수 함수(with_mcp_unregistered)는 입력 dict를 변경하지
않고 새 dict를 반환하고, 파일 IO는 분리해 백업을 동반한다.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

from pouch.catalog.model import Ownership, ToolEntry


def uninstall_skill_file(entry_id: str, *, skills_dir: Path) -> bool:
    """`<skills_dir>/<id>/`를 디렉토리째 제거한다. 없었으면 False(멱등)."""
    target_dir = skills_dir / entry_id
    if not target_dir.exists():
        return False
    shutil.rmtree(target_dir)
    return True


def with_mcp_unregistered(config: dict, server_id: str) -> dict:
    """mcpServers에서 server_id를 뺀 새 설정을 반환한다(멱등). 다른 서버 보존."""
    if server_id not in config.get("mcpServers", {}):
        return config
    updated = copy.deepcopy(config)
    del updated["mcpServers"][server_id]
    return updated


def unregister_mcp(config_path: Path, server_id: str) -> Path | None:
    """설정 파일에서 서버를 제거한다. 기존 파일이 있었으면 백업하고 경로 반환."""
    config = _load_json(config_path)
    updated = with_mcp_unregistered(config, server_id)

    backup: Path | None = None
    if config_path.exists():
        backup = config_path.with_name(config_path.name + ".bak")
        backup.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    config_path.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return backup


def uninstall_entry(
    entry: ToolEntry, *, skills_dir: Path, mcp_config_path: Path
) -> None:
    """ownership에 따라 활성 표면에서 내린다. 카탈로그는 건드리지 않는다.

    linked면 mcpServers에서, skill(owned/vendored)이면 SKILL.md 디렉토리에서 제거.
    """
    if entry.ownership is Ownership.LINKED:
        if mcp_config_path.exists():
            unregister_mcp(mcp_config_path, entry.id)
        return
    uninstall_skill_file(entry.id, skills_dir=skills_dir)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}
