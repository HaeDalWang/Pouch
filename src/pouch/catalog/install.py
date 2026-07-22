"""설치 — 카탈로그 항목을 실제 위치에 배치한다. ownership이 메커니즘을 가른다.

  owned    : body가 내 것 → catalog body를 SKILL.md로 쓴다.
  vendored : body 미보유 → upstream을 다시 읽어 SKILL.md로 쓴다(catalog엔 본문 없음).
  linked   : 파일이 아님 → 배선 등록. kind가 자리를 가른다:
             mcp → .mcp.json의 mcpServers / hook → settings.json의 hooks (둘 다 백업 동반).

순수 함수(with_mcp_registered 등)는 입력 dict를 변경하지 않고 새 dict를 반환한다.
파일 IO는 분리해 순수 로직만 단위 테스트할 수 있다(hooks/settings.py와 같은 결).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from pouch.catalog.docid import unfold_rule_id
from pouch.catalog.model import Ownership, ToolEntry, ToolKind
from pouch.hooks.settings import load_settings, with_recipe_installed, write_settings


# 파일 모양 — 서랍 안에서 한 항목이 어떤 꼴로 사는가.
LAYOUT_NESTED = "nested"  # `<id>/SKILL.md` — 스킬만 폴더를 한 겹 판다
LAYOUT_FLAT = "flat"  # `<id>.md`
LAYOUT_TREE = "tree"  # 접힌 id를 원래 폴더로 되편다(규칙)


@dataclass(frozen=True)
class _Drawer:
    """한 종류가 표면에서 사는 모양 — 어느 폴더에, 어떤 꼴로, 머리말을 다나."""

    folder: str
    layout: str
    with_frontmatter: bool = True


# 종류별 서랍. 하네스가 이미 나눠둔 자리를 그대로 쓴다(배승도 락 2026-07-21).
# importer가 읽어올 때 쓰는 규칙(_DOC_SUBDIRS)의 거울상이다. 여기 없는 종류는
# 올릴 자리가 없다는 뜻이다 — 엉뚱한 서랍에 놓느니 거절한다.
_DRAWERS: dict[ToolKind, _Drawer] = {
    ToolKind.SKILL: _Drawer("skills", LAYOUT_NESTED),
    ToolKind.AGENT: _Drawer("agents", LAYOUT_FLAT),
    ToolKind.COMMAND: _Drawer("commands", LAYOUT_FLAT),
    # 규칙은 평면 장부에 `<묶음>__<이름>`으로 접혀 있다 — 올릴 땐 되편다(락 2026-07-22).
    # 머리말을 안 단다: 규칙 파일은 하네스가 평문으로 통째로 읽어 지침에 싣기 때문에,
    # `---\nname: …` 을 얹으면 그 글자가 지침 안에 그대로 섞인다.
    ToolKind.RULE: _Drawer("rules", LAYOUT_TREE, with_frontmatter=False),
}


def _drawer_for(entry: ToolEntry) -> _Drawer:
    drawer = _DRAWERS.get(entry.kind)
    if drawer is None:
        raise ValueError(
            f"'{entry.id}'({entry.kind.value})는 올릴 자리가 정해져 있지 않습니다."
        )
    return drawer


def target_path_for(entry: ToolEntry, *, base: Path) -> Path:
    """이 항목을 올릴 자리. 서랍이 없는 종류는 ValueError로 정직하게 거절한다."""
    drawer = _drawer_for(entry)
    root = base / drawer.folder
    if drawer.layout == LAYOUT_NESTED:
        return root / entry.id / "SKILL.md"
    if drawer.layout == LAYOUT_TREE:
        *folders, name = unfold_rule_id(entry.id)
        return root.joinpath(*folders) / f"{name}.md"
    return root / f"{entry.id}.md"


def install_doc_file(entry: ToolEntry, *, base: Path) -> Path:
    """문서형 항목(스킬·에이전트·명령)을 종류에 맞는 서랍에 배치한다.

    `base`는 서랍들을 품은 자리(예: `~/.claude`)다 — 서랍 이름을 경로에서 추론하지
    않는다. owned는 catalog의 body를, vendored는 upstream을 다시 읽어 본문을 채운다.
    vendored인데 upstream이 사라졌으면 FileNotFoundError로 보고한다(조용히 삼키지 않음).
    """
    drawer = _drawer_for(entry)
    return _write_doc(
        entry,
        target_path_for(entry, base=base),
        with_frontmatter=drawer.with_frontmatter,
    )


def install_skill_file(entry: ToolEntry, *, skills_dir: Path) -> Path:
    """skill 항목을 `<skills_dir>/<id>/SKILL.md`로 배치한다.

    스킬 서랍을 직접 받는 기존 계약을 유지한다 — 호출부가 `--skills-dir`로 임의
    위치를 지정할 수 있어, 경로 이름에서 다른 서랍을 추론하면 안 된다.
    """
    return _write_doc(entry, skills_dir / entry.id / "SKILL.md")


def _write_doc(entry: ToolEntry, path: Path, *, with_frontmatter: bool = True) -> Path:
    """본문을 확보해 주어진 자리에 쓴다(서랍 계산과 쓰기를 분리).

    머리말(frontmatter)은 하네스가 그걸 읽어 도구를 알아보는 종류에만 단다.
    규칙처럼 평문 그대로 읽히는 종류엔 얹지 않는다 — 얹으면 지침에 섞인다.
    """
    body = _resolve_body(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not with_frontmatter:
        # 본문만 쓸 땐 끝 개행을 우리가 챙긴다 — 본문을 뽑는 과정에서 벗겨지는데,
        # 머리말 경로는 dumps가 붙여줘서 이쪽만 개행 없이 끝나던 어긋남.
        path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
        return path
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


def register_hook(settings_path: Path, entry: ToolEntry) -> Path | None:
    """훅 항목의 조리법을 settings.json에 배선한다. 백업 경로를 반환한다.

    pouch 자체 훅과 같은 안전장치(불변 조작·백업)를 그대로 탄다.
    """
    settings = load_settings(settings_path)
    updated = with_recipe_installed(settings, entry.recipe or {})
    return write_settings(settings_path, updated)


def install_entry(
    entry: ToolEntry,
    *,
    skills_dir: Path,
    mcp_config_path: Path,
    now: str | None = None,
    state_path: Path | None = None,
    settings_path: Path | None = None,
    surface_base: Path | None = None,
) -> Path:
    """ownership과 종류에 따라 설치하고, 결과 경로를 반환한다.

    skill(owned/vendored)이면 SKILL.md 경로, linked면 배선한 설정 경로를 돌려준다
    (mcp → .mcp.json / hook → settings.json). 에이전트·명령은 각자의 서랍으로 간다 —
    `surface_base`(서랍들을 품은 자리, 기본은 스킬 서랍의 부모)가 기준이다.
    설치는 활성 표면에 올리는 유일한 관문이라, 여기서 state.json에 active로 기록한다
    (evolve가 볼 데이터를 심는다). 재부착이면 installed_at을 갱신해 시계를 리셋한다.
    시계는 이 경계에서만 읽는다(now 미지정 시).
    """
    from datetime import datetime

    from pouch import paths
    from pouch.evolution.state import record_installed

    if entry.kind is ToolKind.HOOK:
        target = settings_path or paths.claude_settings_path()
        register_hook(target, entry)
        result = target
    elif entry.ownership is Ownership.LINKED:
        register_mcp(mcp_config_path, entry)
        result = mcp_config_path
    elif entry.kind is ToolKind.SKILL:
        result = install_skill_file(entry, skills_dir=skills_dir)
    else:
        # 에이전트·명령은 스킬과 다른 서랍에 산다(2026-07-21). 전에는 여기로 오는
        # 것이 전부 스킬 폴더에 스킬인 척 쓰였다 — 하네스가 그 자리를 안 읽으므로
        # 올려도 살지 않았다. 서랍이 없는 종류는 target_path_for가 거절한다.
        result = install_doc_file(entry, base=surface_base or skills_dir.parent)

    stamp = now or datetime.now().isoformat(timespec="seconds")
    record_installed(entry.id, now=stamp, state_path=state_path)
    return result


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}
