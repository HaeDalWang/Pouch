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

from pouch.catalog.model import Ownership, ToolEntry, ToolKind
from pouch.hooks.settings import load_settings, with_recipe_removed, write_settings


def unregister_hook(settings_path: Path, entry: ToolEntry) -> Path | None:
    """훅 항목의 배선만 settings.json에서 걷어낸다(백업 동반). 나머지 보존."""
    settings = load_settings(settings_path)
    updated = with_recipe_removed(settings, entry.recipe or {})
    return write_settings(settings_path, updated)


def uninstall_skill_file(entry_id: str, *, skills_dir: Path) -> bool:
    """`<skills_dir>/<id>/`를 디렉토리째 제거한다. 없었으면 False(멱등)."""
    target_dir = skills_dir / entry_id
    if not target_dir.exists():
        return False
    shutil.rmtree(target_dir)
    return True


def uninstall_doc_file(entry: ToolEntry, *, base: Path) -> bool:
    """문서형 항목을 제 서랍에서 걷어낸다 — install_doc_file의 거울상.

    올릴 때 쓴 자리 계산(target_path_for)을 그대로 되쓴다. 자리 규칙이 한 곳에만
    있어야 "올린 데"와 "내리는 데"가 어긋나지 않는다. 규칙처럼 폴더 안에 사는
    종류도 **파일 하나만** 지운다 — 폴더째 지우면 같은 묶음의 이웃 규칙이
    말없이 쓸려간다.
    """
    from pouch.catalog.install import target_path_for

    try:
        target = target_path_for(entry, base=base)
    except ValueError:
        # 올릴 자리가 없던 종류는 내릴 것도 없다(파일로 살지 않는다).
        return False
    if not target.exists():
        return False
    target.unlink()
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
    entry: ToolEntry,
    *,
    skills_dir: Path,
    mcp_config_path: Path,
    settings_path: Path | None = None,
    surface_base: Path | None = None,
) -> None:
    """ownership에 따라 활성 표면에서 내린다. 카탈로그는 건드리지 않는다.

    hook이면 settings.json 배선에서, linked(mcp)면 mcpServers에서,
    skill(owned/vendored)이면 SKILL.md 디렉토리에서 제거. 에이전트·명령·규칙은
    각자의 서랍에서 파일 하나만 걷어낸다(2026-07-22 수리 — 전에는 여기까지 오는
    것을 전부 스킬 서랍에서만 찾아, 다른 서랍 파일은 내려도 표면에 남았다).
    """
    if entry.kind is ToolKind.HOOK:
        from pouch import paths

        target = settings_path or paths.claude_settings_path()
        if target.exists():
            unregister_hook(target, entry)
        return
    if entry.ownership is Ownership.LINKED:
        if mcp_config_path.exists():
            unregister_mcp(mcp_config_path, entry.id)
        return
    if entry.kind is ToolKind.SKILL:
        uninstall_skill_file(entry.id, skills_dir=skills_dir)
        return
    uninstall_doc_file(entry, base=surface_base or skills_dir.parent)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}
