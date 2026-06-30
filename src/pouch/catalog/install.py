"""설치 — 카탈로그 항목을 실제 위치에 배치한다. ownership이 메커니즘을 가른다.

  owned    : body가 내 것 → catalog body를 SKILL.md로 쓴다.
  vendored : body 미보유 → upstream을 다시 읽어 SKILL.md로 쓴다(catalog엔 본문 없음).
  linked   : 파일이 아님 → .mcp.json의 mcpServers에 recipe를 등록한다(백업 동반).

순수 함수(with_mcp_registered 등)는 입력 dict를 변경하지 않고 새 dict를 반환한다.
파일 IO는 분리해 순수 로직만 단위 테스트할 수 있다(hooks/settings.py와 같은 결).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import frontmatter

from pouch.catalog.model import Ownership, ToolEntry


def install_skill_file(entry: ToolEntry, *, skills_dir: Path) -> Path:
    """skill 항목을 `<skills_dir>/<id>/SKILL.md`로 배치한다.

    owned는 catalog의 body를, vendored는 upstream을 다시 읽어 본문을 채운다.
    vendored인데 upstream이 사라졌으면 FileNotFoundError로 보고한다(조용히 삼키지 않음).
    """
    body = _resolve_body(entry)

    target_dir = skills_dir / entry.id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "SKILL.md"

    meta = {"name": entry.id, "description": entry.description}
    path.write_text(frontmatter.dumps(frontmatter.Post(body, **meta)), encoding="utf-8")
    return path


def _resolve_body(entry: ToolEntry) -> str:
    """설치할 본문을 ownership에 맞게 확보한다."""
    if entry.ownership is Ownership.OWNED:
        return entry.body or ""
    if entry.ownership is Ownership.VENDORED:
        if not entry.upstream:
            raise ValueError(f"'{entry.id}'에 upstream이 없어 설치할 수 없습니다.")
        upstream_path = Path(entry.upstream)
        if not upstream_path.exists():
            raise FileNotFoundError(
                f"'{entry.id}'의 upstream이 사라졌습니다: {entry.upstream}"
            )
        # vendored는 catalog에 본문이 없으니 upstream에서 최신 본문을 다시 읽는다.
        return frontmatter.loads(upstream_path.read_text(encoding="utf-8")).content
    raise ValueError(
        f"'{entry.id}'는 {entry.ownership.value}입니다. skill 파일 설치 대상이 아닙니다."
    )


def is_mcp_registered(config: dict, server_id: str) -> bool:
    """MCP 서버가 이미 등록돼 있는지."""
    return server_id in config.get("mcpServers", {})


def with_mcp_registered(config: dict, entry: ToolEntry) -> dict:
    """linked 항목을 mcpServers에 등록한 새 설정을 반환한다(멱등). 기존 서버 보존."""
    if entry.ownership is not Ownership.LINKED:
        raise ValueError(
            f"'{entry.id}'는 {entry.ownership.value}입니다. MCP 등록은 linked만 대상으로 합니다."
        )
    if is_mcp_registered(config, entry.id):
        return config
    updated = copy.deepcopy(config)
    servers = updated.setdefault("mcpServers", {})
    servers[entry.id] = dict(entry.recipe or {})
    return updated


def register_mcp(config_path: Path, entry: ToolEntry) -> Path | None:
    """linked 항목을 설정 파일에 등록한다. 기존 파일이 있었으면 백업하고 경로 반환."""
    config = _load_json(config_path)
    updated = with_mcp_registered(config, entry)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if config_path.exists():
        backup = config_path.with_name(config_path.name + ".bak")
        backup.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    config_path.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return backup


def install_entry(
    entry: ToolEntry, *, skills_dir: Path, mcp_config_path: Path
) -> Path:
    """ownership에 따라 설치하고, 결과 경로를 반환한다.

    skill(owned/vendored)이면 SKILL.md 경로, linked면 MCP 설정 경로를 돌려준다.
    """
    if entry.ownership is Ownership.LINKED:
        register_mcp(mcp_config_path, entry)
        return mcp_config_path
    return install_skill_file(entry, skills_dir=skills_dir)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}
