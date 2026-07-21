"""도구통 훑기 — 이미 깔려 있는 것을 찾아 소스 대기실까지만 재운다.

**왜 있나.** pouch는 이미 깔린 스킬·MCP를 하나도 안 찾아봤다. 런타임(python·node)은
감지하면서 도구는 사람이 `catalog import <경로>`로 손수 찍어줘야만 들어왔다. 그래서
도구가 백 개 있는 사람도 빈 주머니로 시작했다(2026-07-21 동료 환경에서 실측 — 스킬
160개가 깔린 머신의 카탈로그가 5개였다).

**어디까지 자동인가 (배승도 락, 2026-07-21).** 훑기는 **찾아서 재우기**까지만 한다.
카탈로그 진입도, 표면(연장통) 올리기도 하지 않는다 — 그건 그대로 실사용이 결정한다
(import 관문 (다) 유지, "실사용이 증거다" 유지). 오너 되풂: *"대기실에만 올리면 그
뒤에는 evolve에서 처리될 테니까. 대기실까지 올리는 거는 최대한 자동화시키는 게 좋아.
이러한 도구를 모르는 사람들은 영원히 빈칸으로 살 거야."*

**하네스 이름이 여기 없다.** 어디를 훑을지는 어댑터의 `toolbox_paths()`가 안다.
새 하네스는 그 칸만 채우면 훑기에 편입된다 — 이 파일은 손대지 않는다.

**인질 금지.** 조각 하나가 깨져도 나머지는 계속 간다. 건너뛴 것은 이유와 함께
보고한다(plugin import·세트 적용과 같은 정신).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pouch import paths
from pouch.catalog.commands import find_plugin_roots
from pouch.catalog.importer import (
    import_hooks,
    import_vendored_doc,
    import_mcp_servers,
    import_plugin,
    import_vendored_skill,
)
from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.hosts.base import (
    LAYOUT_DOCS_FLAT,
    LAYOUT_FILE,
    LAYOUT_PLUGIN_CACHE,
    LAYOUT_SKILLS_ROOT,
    Toolbox,
    ToolboxHost,
)

_SKILL_FILENAME = "SKILL.md"
_MCP_FILENAME = ".mcp.json"
_HOOKS_FILENAME = "hooks.json"

# 후보 종류 — layout에서 파생되며, 각각 기존 importer 하나에 대응한다.
_KIND_SKILL = "skill"
_KIND_PLUGIN = "plugin"
_KIND_MCP = "mcp"
_KIND_HOOKS = "hooks"
_KIND_DOC = "doc"  # 자리가 종류를 정하는 평면 문서(agents·commands·rules)


@dataclass(frozen=True)
class SweepReport:
    """훑기 결과 — 새로 재운 것, 이미 알던 것, 못 담아 건너뛴 것."""

    staged: tuple[str, ...] = ()
    already: int = 0
    skipped: tuple[str, ...] = ()
    per_host: dict[str, int] = field(default_factory=dict)

    @property
    def found(self) -> int:
        """이번에 만난 도구 총수(새로 재운 것 + 이미 알던 것)."""
        return len(self.staged) + self.already


_README = "README.md"  # 폴더 안내문은 도구가 아니다(플러그인 import와 같은 관례)


@dataclass(frozen=True)
class _Candidate:
    """import할 대상 하나 — 무엇으로(kind) 어디를(path) 들일지."""

    kind: str
    path: Path
    tool_kind: "ToolKind | None" = None


def _candidates(box: Toolbox) -> list[_Candidate]:
    """도구통 하나에서 import할 후보를 뽑는다 — layout이 뽑는 법을 정한다.

    경로만 보고는 판별할 수 없다: `~/.claude`는 skills/를 품었다는 이유로 plugin으로
    오인되고, `~/.claude/skills`는 스킬이 아니라 스킬들의 부모다. 그래서 layout이
    같이 온다. 없는 도구통은 조용히 빈 목록 — 안 깔린 게 흠은 아니다.
    """
    if not box.path.exists():
        return []
    if box.layout == LAYOUT_FILE:
        return [_Candidate(_file_kind(box.path), box.path)]
    if box.layout == LAYOUT_PLUGIN_CACHE:
        return [_Candidate(_KIND_PLUGIN, root) for root in find_plugin_roots(box.path)]
    if box.layout == LAYOUT_SKILLS_ROOT:
        return [
            _Candidate(_KIND_SKILL, child / _SKILL_FILENAME)
            for child in sorted(box.path.iterdir())
            if child.is_dir() and (child / _SKILL_FILENAME).exists()
        ]
    if box.layout == LAYOUT_DOCS_FLAT:
        # 하위 폴더까지 훑는다 — 규칙은 `rules/<언어>/<이름>.md`로 한 겹 더 들어간다.
        # 종류는 파일이 아니라 자리가 답한다(box.kind).
        return [
            _Candidate(_KIND_DOC, path, box.kind)
            for path in sorted(box.path.rglob("*.md"))
            if path.is_file() and path.name != _README
        ]
    return []


def _file_kind(path: Path) -> str:
    """파일 도구통의 종류를 이름으로 가른다."""
    if path.name == _MCP_FILENAME:
        return _KIND_MCP
    if path.name == _HOOKS_FILENAME:
        return _KIND_HOOKS
    return _KIND_SKILL


def _import_candidate(
    candidate: _Candidate,
    store: CatalogStore,
    *,
    synced_at: str,
    host_name: str,
) -> tuple[Sequence[ToolEntry], list[str]]:
    """후보 하나를 기존 importer로 들인다. (담은 것, 건너뛴 이유들)."""
    kind, path = candidate.kind, candidate.path
    tags = (f"host:{host_name}",)
    if kind == _KIND_DOC:
        if candidate.tool_kind is None:
            raise ValueError("이 자리에 어떤 종류가 사는지 정해지지 않았습니다")
        entry = import_vendored_doc(
            path, store, kind=candidate.tool_kind, upstream=str(path),
            synced_at=synced_at, source="sweep", tags=tags,
        )
        return [entry], []
    if kind == _KIND_PLUGIN:
        result = import_plugin(path, store, synced_at=synced_at, source="sweep", tags=tags)
        return result.entries, [_reason(s.path, s.reason) for s in result.skipped]
    if kind == _KIND_MCP:
        return import_mcp_servers(path, store, source="sweep", tags=tags), []
    if kind == _KIND_HOOKS:
        return import_hooks(path, store, source="sweep", tags=tags), []
    entry = import_vendored_skill(
        path, store, upstream=str(path), synced_at=synced_at, source="sweep", tags=tags
    )
    return [entry], []


def has_swept() -> bool:
    """이 주머니가 도구통을 한 번이라도 훑은 적 있나.

    표식이 없거나 깨졌으면 "안 훑음"으로 본다 — 한 번 더 권하는 쪽이 안전하다
    (권유는 되돌릴 게 없고, 놓치면 사람이 빈 주머니로 산다).
    """
    path = paths.sweep_marker_path()
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("last_swept_at"))
    except (json.JSONDecodeError, OSError, AttributeError):
        return False


def record_swept(*, now: str) -> None:
    """훑었다고 표식을 남긴다(실패해도 훑기 자체를 망치지 않는다)."""
    path = paths.sweep_marker_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"last_swept_at": now}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _reason(path: Path | str, message: str) -> str:
    """건너뛴 이유 한 줄 — importer가 이미 경로를 담았으면 두 번 찍지 않는다."""
    return message if str(path) in message else f"{path}: {message}"


def sweep_toolboxes(
    *,
    source_store: CatalogStore,
    hosts: Iterable[ToolboxHost],
    synced_at: str,
) -> SweepReport:
    """하네스들의 도구통을 훑어 소스 대기실에 재운다(카탈로그는 건드리지 않는다).

    멱등하다 — 두 번 훑어도 두 번 재우지 않는다. 이미 대기실에 있던 id는 `already`로
    세고, 이번에 처음 본 것만 `staged`에 담는다.
    """
    known = {entry.id for entry in source_store.list()}
    staged: list[str] = []
    skipped: list[str] = []
    per_host: dict[str, int] = {}
    already = 0

    for host in hosts:
        newly_staged = 0
        for box in host.toolbox_paths():
            for candidate in _candidates(box):
                try:
                    entries, box_skips = _import_candidate(
                        candidate, source_store, synced_at=synced_at, host_name=host.name
                    )
                except (ValueError, OSError, KeyError) as exc:
                    skipped.append(_reason(candidate.path, str(exc)))
                    continue
                skipped.extend(box_skips)
                for entry in entries:
                    if entry.id in known:
                        already += 1
                        continue
                    known.add(entry.id)
                    staged.append(entry.id)
                    newly_staged += 1
        if newly_staged:
            per_host[host.name] = newly_staged

    return SweepReport(
        staged=tuple(staged),
        already=already,
        skipped=tuple(skipped),
        per_host=per_host,
    )
