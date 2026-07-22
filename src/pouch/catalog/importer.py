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

from pouch.catalog.docid import fold_rule_id
from pouch.catalog.model import SURFACE_PLUGIN, Overlay, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore

# AWS 리전 패턴 (us-east-1, eu-west-2, ap-southeast-1 …) — MCP 엔드포인트에서 추출.
_AWS_REGION_RE = re.compile(r"\b([a-z]{2}-[a-z]+-\d+)\b")

# 파일명에 못 쓰는(또는 위험한) 글자를 -로 접는다 — 훅 그룹 id("pre:bash:check")용.
_ID_UNSAFE_RE = re.compile(r"[^a-zA-Z0-9_-]+")

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
        # 되펴기(install)와 같은 파일에 산다 — 한쪽만 바뀌면 왕복이 어긋난다.
        return fold_rule_id(path.parent.name, path.stem)
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
    if existing is not None and existing.kind is not kind:
        # 장부는 평면(`<id>.md`)이라 종류가 달라도 이름이 같으면 한 자리를 다툰다.
        # 실측 2026-07-21: agent-sort·context-budget·rules-distill이 스킬과 명령으로
        # 둘 다 존재해, 훑기가 스킬을 소리 없이 명령으로 덮었다. 조용한 손실보다
        # 시끄러운 거절이 낫다 — 먼저 담긴 것을 지키고 이유를 알린다.
        raise ValueError(
            f"'{entry_id}'는 이미 {existing.kind.value}로 담겨 있어 "
            f"{kind.value}로 덮지 않았습니다(이름이 겹칩니다): {path}"
        )
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
    CLI 단독 입양(`pouch catalog import ./SKILL.md`)과 sync 재방문이 이 vendored
    경로를 쓴다. plugin 번들 안의 doc은 이 경로가 아니라 import_plugin_doc(관측
    스텁)으로 간다 — plugin이 표면을 소유하므로 pouch가 body를 주장하면 안 된다.
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


def import_plugin_doc(
    path: Path,
    store: CatalogStore,
    *,
    kind: ToolKind,
    source: str,
    tags: tuple[str, ...] = (),
) -> ToolEntry:
    """plugin 번들 안의 문서형 도구(skill/command/agent/rule)를 관측 스텁으로 들인다.

    (B) 관리 레이어 정렬(2026-07-13): plugin이 표면을 소유하므로 pouch는 body를
    vendored로 주장하지 않는다. 이중 소유(pouch vendored + marketplace 표면)를
    피하려고 linked+recipe={}+surface=plugin으로만 담는다:
      - ownership=linked : "실행은 외부(플러그인 런타임)에 위임"이 (B)와 일치.
      - recipe={}        : pouch가 기동하지 않는다(빈 조리법). install 경로가
                           surface=plugin을 막아 빈 recipe로 오등록되지 않는다.
      - surface=plugin   : 진화 조언(plan_advice)이 이걸 신호로 본다. drop 후보
                           (active 표면만 봄)에는 안 걸려 거짓 drop이 없다.
      - kind 보존        : 추천 풀·신호 판별(has_usage_signal)이 종류를 본다.

    id는 kind별 규칙 그대로(_resolve_doc_id). 스킬은 usage에 bare id로 찍히므로
    (Skill 툴 tool_input.skill) MCP식 plugin_<플러그인>_<도구> alias를 지어 붙이지
    않는다 — 실데이터로 확인 안 된 접두어를 지어내면 그 지어내기가 카탈로그에
    박힌다(정정2 교훈: 셸/추측으로 단정 금지). 재import는 기존 overlay·tags를
    보존한다("떨어져도 개인화는 남는다").
    """
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata
    entry_id = _resolve_doc_id(path, meta, kind)
    title = str(meta.get("title") or meta.get("name") or entry_id)
    description = str(meta.get("description", ""))

    existing = store.get(entry_id)
    preserved_overlay = existing.overlay if existing else None
    preserved_tags = existing.tags if existing else tags

    entry = ToolEntry.linked(
        id=entry_id,
        kind=kind,
        source=source,
        title=title,
        description=description,
        recipe={},
        tags=preserved_tags,
        surface=SURFACE_PLUGIN,
    )
    # linked 팩토리는 overlay를 안 받는다(vendored 필드) — 보존분만 얹어 새 엔트리로.
    if preserved_overlay is not None:
        entry = replace(entry, overlay=preserved_overlay)
    store.save(entry)
    return entry


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


def _hook_entry_id(event: str, group: dict) -> str:
    """훅 그룹의 정체(id)를 정한다 — 그룹 id 우선, 없으면 사건+대상 합성.

    합성이 안전한 이유: 훅은 사용 기록(usage.jsonl)에 이름이 찍히지 않아
    이름을 런타임과 맞출 필요가 없다(스킬의 name 요구와 다른 이유). 대신
    결정적이어야 재import가 같은 항목을 덮는다(중복 방지).
    """
    raw = group.get("id") or f"hook-{event}-{group.get('matcher', 'all')}"
    return _ID_UNSAFE_RE.sub("-", raw).strip("-").lower()


def import_hooks(
    hooks_json_path: Path,
    store: CatalogStore,
    *,
    source: str,
    tags: tuple[str, ...] = (),
    plugin_name: str | None = None,
) -> list[ToolEntry]:
    """hooks.json의 각 그룹을 linked 훅 항목으로 등록한다.

    훅 = "이 사건이 나면 이 명령을 실행하라"는 배선. 몸(파일)이 아니라
    조리법이라 mcp와 같은 결(linked + recipe)로 담는다. recipe에 사건·대상·
    명령을 원문 그대로 들고 있어야 설치 때 사용자에게 원문을 보여줄 수 있다.

    플러그인에서 온 훅(plugin_name 지정)은 surface=plugin — 플러그인 시스템이
    이미 실행 중이라 pouch가 또 배선하면 같은 훅이 두 번 돈다.
    """
    data = json.loads(hooks_json_path.read_text(encoding="utf-8"))

    entries: list[ToolEntry] = []
    for event, groups in data.get("hooks", {}).items():
        for group in groups:
            recipe: dict = {"event": event, "hooks": group.get("hooks", [])}
            if group.get("matcher"):
                recipe["matcher"] = group["matcher"]
            description = str(group.get("description", ""))
            entry = ToolEntry.linked(
                id=_hook_entry_id(event, group),
                kind=ToolKind.HOOK,
                source=source,
                title=group.get("id") or f"{event} 훅",
                description=description,
                recipe=recipe,
                tags=tags,
                surface=SURFACE_PLUGIN if plugin_name else None,
            )
            store.save(entry)
            entries.append(entry)
    return entries


def _import_bundle_doc(
    doc_md: Path,
    store: CatalogStore,
    *,
    kind: ToolKind,
    synced_at: str,
    source: str,
    tags: tuple[str, ...],
    plugin_name: str | None,
) -> ToolEntry:
    """번들 안 문서형 도구를 표면 소유자에 맞게 담는다(MCP 대칭).

    plugin_name(=manifest .claude-plugin/plugin.json에서 읽음)이 있으면 진짜
    플러그인이 표면을 소유 → 관측 스텁(surface=plugin). manifest가 없으면
    사용자가 모아둔 스킬 폴더 → vendored(pouch 소유, 설치 가능). import_mcp_servers
    가 `surface = plugin if plugin_name else None`로 가르는 것과 같은 기준이다.
    """
    if plugin_name is not None:
        return import_plugin_doc(doc_md, store, kind=kind, source=source, tags=tags)
    return import_vendored_doc(
        doc_md, store, kind=kind, upstream=str(doc_md),
        synced_at=synced_at, source=source, tags=tags,
    )


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

    plugin_name = _plugin_name(plugin_dir)

    mcp_json = plugin_dir / ".mcp.json"
    if mcp_json.exists():
        entries.extend(
            import_mcp_servers(
                mcp_json, store, source=source, tags=tags,
                plugin_name=plugin_name,
            )
        )

    hooks_json = plugin_dir / "hooks" / "hooks.json"
    if hooks_json.exists():
        try:
            entries.extend(
                import_hooks(
                    hooks_json, store, source=source, tags=tags,
                    # 표면 관리 판단엔 "플러그인에서 왔다"는 사실만 필요하다.
                    # 이름을 못 읽었어도 이중 배선 위험은 같으므로 관측만으로 둔다.
                    plugin_name=plugin_name or plugin_dir.name,
                )
            )
        except (json.JSONDecodeError, OSError) as exc:
            skipped.append(SkippedSkill(path=str(hooks_json), reason=str(exc)))

    for subdir, pattern, kind in _DOC_SUBDIRS:
        doc_dir = plugin_dir / subdir
        if not doc_dir.is_dir():
            continue
        for doc_md in sorted(doc_dir.glob(pattern)):
            try:
                entries.append(
                    _import_bundle_doc(
                        doc_md, store, kind=kind, synced_at=synced_at,
                        source=source, tags=tags, plugin_name=plugin_name,
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
