"""vendored-import — upstream을 추적하는 도구를 카탈로그에 들인다.

핵심 원칙(vendored): 본체(body)는 절대 복사/저장하지 않는다. upstream 경로만
참조로 들고, 개인화(태그·boundary·메모)는 본체와 분리된 overlay에 쌓는다.
재import는 upstream 갱신만 반영하고 overlay는 보존한다(멱등).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

import frontmatter

from pouch.catalog.model import SURFACE_PLUGIN, Overlay, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore

# AWS 리전 패턴 (us-east-1, eu-west-2, ap-southeast-1 …) — MCP 엔드포인트에서 추출.
_AWS_REGION_RE = re.compile(r"\b([a-z]{2}-[a-z]+-\d+)\b")

# plugin 안에서 문서형 도구가 사는 자리 — (하위디렉토리, glob, kind).
# 스킬만 `<이름>/SKILL.md`로 한 겹 더 들어가고, 명령·에이전트는 평면 `*.md`.
# ToolKind는 함수 정의부에서 import되지만 상수는 지연 참조를 피하려 아래서 채운다.
_DOC_SUBDIRS = (
    ("skills", "*/SKILL.md", ToolKind.SKILL),
    ("commands", "*.md", ToolKind.COMMAND),
    ("agents", "*.md", ToolKind.AGENT),
    # 규칙은 rules/<lang>/<name>.md 한 겹 — `*/*.md`가 최상위 README.md를 제외한다.
    ("rules", "*/*.md", ToolKind.RULE),
)


@dataclass(frozen=True)
class SkillSource:
    """SKILL.md에서 읽은 메타데이터(본문 제외)."""

    id: str
    title: str
    description: str
    upstream: str


@dataclass(frozen=True)
class SkippedSkill:
    """import에서 건너뛴 조각 — 조용히 삼키지 않고 이유와 함께 보고한다."""

    path: str
    reason: str


@dataclass(frozen=True)
class PluginImportResult:
    """plugin 분해 결과: 담은 것 + 건너뛴 것."""

    entries: tuple[ToolEntry, ...]
    skipped: tuple[SkippedSkill, ...] = ()


def _require_name(meta: dict, path: Path) -> str:
    """frontmatter의 name을 요구한다. 없으면 어느 파일인지까지 말해주고 실패.

    디렉토리명으로 추측하지 않는다 — 추측한 식별자가 카탈로그에 들어가면
    usage 추적(tool_input.skill)과 어긋나 유령 엔트리가 된다(java 감지와 같은 원칙).
    """
    name = meta.get("name")
    if not name:
        raise ValueError(f"{path}: frontmatter에 name이 없습니다")
    return str(name)


def read_skill(path: Path, *, upstream: str) -> SkillSource:
    """SKILL.md의 frontmatter만 읽는다. 본문은 의도적으로 버린다(vendored).

    본문을 메모리에 들이지 않기 위해 metadata만 취하고 content는 참조하지 않는다.
    """
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata
    name = _require_name(meta, path)
    return SkillSource(
        id=name,
        title=str(meta.get("title") or name),
        description=str(meta.get("description", "")),
        upstream=upstream,
    )


# frontmatter `name`이 정체(id)의 권위인 kind — 파일명과 달라도 name을 쓴다.
# COMMAND는 여기 없다: 슬래시 명령엔 name 필드가 없고 파일명이 곧 런타임 id다.
_NAME_AUTHORITATIVE_KINDS = frozenset({ToolKind.SKILL, ToolKind.AGENT})


def _resolve_doc_id(path: Path, meta: dict, kind: ToolKind) -> str:
    """문서형 도구(skill/agent/command)의 정체(id)를 kind에 따라 해석한다.

    skill·agent는 frontmatter name이 권위(없으면 실패 — 디렉토리명 추측 금지 원칙).
    command는 name 필드가 없으므로 파일명 stem이 정체다(추측이 아니라 런타임이
    실제로 쓰는 슬래시 명령 이름 — 예: santa-loop.md → santa-loop).
    """
    if kind in _NAME_AUTHORITATIVE_KINDS:
        return _require_name(meta, path)
    if kind is ToolKind.RULE:
        # coding-style.md가 python/·common/… 여러 곳에 겹친다. 부모 디렉토리로
        # 스코프해 유니크하게 만들되, store가 평면(`<id>.md`)이라 "/" 대신 "__".
        return f"{path.parent.name}__{path.stem}"
    return path.stem


def import_vendored_doc(
    path: Path,
    store: CatalogStore,
    *,
    kind: ToolKind,
    upstream: str,
    synced_at: str,
    source: str = "aws",
    tags: tuple[str, ...] = ("vendor:aws",),
) -> ToolEntry:
    """문서형 도구(skill/agent/command)를 vendored 항목으로 들인다.

    셋 다 `.md` 하나 = 도구 하나, 본체(body)를 안 들이는 계약이 같다. 유일한
    차이는 id 해석(_resolve_doc_id)뿐이라 한 함수로 묶는다. 재import 시 기존
    overlay·tags를 보존한다(멱등).
    """
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata
    entry_id = _resolve_doc_id(path, meta, kind)
    title = str(meta.get("title") or meta.get("name") or entry_id)
    description = str(meta.get("description", ""))

    existing = store.get(entry_id)
    preserved_overlay = existing.overlay if existing else None
    preserved_tags = existing.tags if existing else tags

    entry = ToolEntry.vendored(
        id=entry_id,
        kind=kind,
        source=source,
        title=title,
        description=description,
        upstream=upstream,
        synced_at=synced_at,
        overlay=preserved_overlay,
        tags=preserved_tags,
    )
    store.save(entry)
    return entry


def import_vendored_skill(
    path: Path,
    store: CatalogStore,
    *,
    upstream: str,
    synced_at: str,
    source: str = "aws",
    tags: tuple[str, ...] = ("vendor:aws",),
) -> ToolEntry:
    """SKILL.md를 vendored 항목으로 들인다(import_vendored_doc의 skill 특화).

    기존 호출부·테스트 호환을 위해 유지한다 — 실제 일은 import_vendored_doc이 한다.
    """
    return import_vendored_doc(
        path,
        store,
        kind=ToolKind.SKILL,
        upstream=upstream,
        synced_at=synced_at,
        source=source,
        tags=tags,
    )


def import_owned_skill(
    path: Path,
    store: CatalogStore,
    *,
    source: str,
    tags: tuple[str, ...] = (),
    force: bool = False,
) -> ToolEntry:
    """SKILL.md를 owned 항목으로 입양한다 — body 통째로 소유, upstream 끊음.

    vendored의 거울상이다. 입양한 순간부터 본문은 내 것이라 직접 깎아 진화시킨다.
    그래서 재import는 기본적으로 거부한다(force=False): 내가 깎은 body를 말없이
    덮으면 안 되므로. 정말 upstream 본문으로 되돌리려면 force=True를 명시해야 한다.
    """
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata
    name = _require_name(meta, path)

    if not force and store.get(name) is not None:
        raise FileExistsError(
            f"'{name}'은 이미 owned로 입양돼 있습니다. "
            "직접 깎은 본문을 덮으려면 force=True를 명시하세요."
        )

    entry = ToolEntry.owned(
        id=name,
        kind=ToolKind.SKILL,
        source=source,
        title=str(meta.get("title") or name),
        description=str(meta.get("description", "")),
        body=post.content,
        tags=tags,
    )
    store.save(entry)
    return entry


def _plugin_name(plugin_dir: Path) -> str | None:
    """plugin의 정식 이름을 .claude-plugin/plugin.json에서 읽는다.

    디렉토리명으로 추측하지 않는다(캐시 구조에선 버전 디렉토리가 루트라 틀린다).
    못 읽으면 None — alias 없이 들이는 게 틀린 alias보다 낫다.
    """
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("name") or None
    except (OSError, json.JSONDecodeError):
        return None


def _extract_region(recipe: dict) -> str | None:
    """MCP recipe(command+args)에서 AWS 리전을 추출한다. 없으면 None.

    엔드포인트 URL이나 인자 어딘가에 박힌 `us-east-1` 같은 토큰을 찾는다.
    linked는 '어느 region에서 실행되나'를 알아야 하므로 여기서 한 번 파싱해 둔다.
    """
    haystack = " ".join(str(a) for a in recipe.get("args", []))
    match = _AWS_REGION_RE.search(haystack)
    return match.group(1) if match else None


def import_mcp_servers(
    mcp_json_path: Path,
    store: CatalogStore,
    *,
    source: str,
    tags: tuple[str, ...] = (),
    plugin_name: str | None = None,
) -> list[ToolEntry]:
    """.mcp.json의 각 서버를 linked 항목으로 등록한다 — 실행은 외부에 위임.

    body가 없는 게 당연하다(linked). recipe(command+args)와 region만 들고,
    실제 기동은 Claude/MCP 런타임이 한다.

    plugin에서 온 서버(plugin_name 지정)는 두 가지가 달라진다:
      - alias `plugin_<플러그인>_<서버>` — Claude Code 런타임이 노출하는 이름.
        이게 없으면 usage 추적과 카탈로그가 같은 도구를 다른 이름으로 부른다.
      - surface=plugin — 표면을 플러그인이 관리하므로 pouch는 관측만 한다.
    """
    data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
    servers = data.get("mcpServers", {})

    entries: list[ToolEntry] = []
    for name, spec in servers.items():
        recipe = {k: v for k, v in spec.items() if k in ("command", "args")}
        entry = ToolEntry.linked(
            id=name,
            kind=ToolKind.MCP,
            source=source,
            title=name,
            description=spec.get("description", ""),
            recipe=recipe,
            region=_extract_region(recipe),
            tags=tags,
            aliases=(f"plugin_{plugin_name}_{name}",) if plugin_name else (),
            surface=SURFACE_PLUGIN if plugin_name else None,
        )
        store.save(entry)
        entries.append(entry)
    return entries


def import_plugin(
    plugin_dir: Path,
    store: CatalogStore,
    *,
    synced_at: str,
    source: str = "aws",
    tags: tuple[str, ...] = ("vendor:aws",),
) -> PluginImportResult:
    """plugin을 원자 단위로 분해해 카탈로그에 들인다.

    plugin은 ownership이 아니라 '번들'이다. 카탈로그엔 plugin 엔트리를 남기지
    않고, 구성 요소만 1급 시민으로 쪼갠다:
      - .mcp.json의 각 서버 → linked
      - skills/*/SKILL.md → 각각 vendored (재import는 overlay 보존)

    스킬은 import_vendored_skill에 위임해 overlay 보존을 공짜로 얻는다.
    깨진 스킬(name 없음, 파싱 실패)은 건너뛰되 이유와 함께 보고한다 —
    실측(ECC): 182개 중 1개가 깨졌다고 나머지 181개를 인질로 잡으면 안 된다.
    """
    entries: list[ToolEntry] = []
    skipped: list[SkippedSkill] = []

    mcp_json = plugin_dir / ".mcp.json"
    if mcp_json.exists():
        entries.extend(
            import_mcp_servers(
                mcp_json, store, source=source, tags=tags,
                plugin_name=_plugin_name(plugin_dir),
            )
        )

    for subdir, pattern, kind in _DOC_SUBDIRS:
        doc_dir = plugin_dir / subdir
        if not doc_dir.is_dir():
            continue
        for doc_md in sorted(doc_dir.glob(pattern)):
            try:
                entries.append(
                    import_vendored_doc(
                        doc_md,
                        store,
                        kind=kind,
                        upstream=str(doc_md),
                        synced_at=synced_at,
                        source=source,
                        tags=tags,
                    )
                )
            except Exception as exc:  # noqa: BLE001 — 외부 번들은 신뢰 경계 밖
                skipped.append(SkippedSkill(path=str(doc_md), reason=str(exc)))

    return PluginImportResult(entries=tuple(entries), skipped=tuple(skipped))


def apply_overlay(store: CatalogStore, entry_id: str, overlay: Overlay) -> ToolEntry:
    """vendored 항목에 개인화 overlay를 붙인다. 본체(upstream)는 건드리지 않는다."""
    entry = store.get(entry_id)
    if entry is None:
        raise ValueError(f"카탈로그에 '{entry_id}' 항목이 없습니다.")
    updated = replace(entry, overlay=overlay)
    store.save(updated)
    return updated
