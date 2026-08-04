"""표면 조회 — "이 도구가 지금 어느 하네스에 올라가 있나".

**저장하지 않고 매번 실측한다.** 표면은 파일 시스템이 곧 진실이라, 어딘가 적어두면
사용자가 직접 도구를 지운 순간 거짓이 된다. 훑기(sweep)가 보는 그 자리를 되짚어
보면 지금 상태를 바로 알 수 있으므로, 낡을 수 있는 사본을 만들지 않는다.

**어디를 볼지는 어댑터가 안다.** `toolbox_paths()`를 그대로 재사용한다 — 새 하네스가
그 칸을 채우면 이 조회에도 자동으로 편입된다(하네스 이름을 여기 쓰지 않는다).

이 조회가 여는 것: 같은 도구가 한 표면엔 있고 다른 표면엔 없다는 걸 알 수 있어야
"Claude에서 자주 쓴 이 스킬이 Codex 표면엔 없네"를 말할 수 있고, 반대로 기록이
안 남는 표면의 도구를 "안 쓴다"고 잘못 판정하는 것도 막을 수 있다(BACKLOG P5).
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch.catalog.docid import unfold_rule_id
from pouch.catalog.model import SURFACE_PLUGIN, Ownership, ToolEntry, ToolKind
from pouch.hosts.base import (
    LAYOUT_DOCS_FLAT,
    LAYOUT_FILE,
    LAYOUT_SKILLS_ROOT,
    Toolbox,
)

_SKILL_FILENAME = "SKILL.md"
_MCP_SERVERS_KEY = "mcpServers"


def installed_surfaces(entry: ToolEntry) -> tuple[str, ...] | None:
    """이 도구가 올라가 있는 표면 이름들(claude·codex…).

    - `("claude",)` — 확인했고, 거기 있다
    - `()` — 확인했고, 어디에도 없다
    - `None` — **판단할 수 없다**(플러그인이 관리하는 자리)

    빈 튜플과 None을 가르는 게 이 함수의 핵심이다. 플러그인 관리 항목은 플러그인이
    자기 방식으로 등록해서 pouch가 보는 자리엔 안 보이는데, 그걸 "없음"으로 답하면
    **매일 쓰는 도구를 "어디에도 없다"고 말하게 된다**(실측: aws-mcp, 2026-08-04).
    그 거짓말은 헛제안("Codex에도 올려볼까요?")이나 drop 후보로 이어진다.

    순서는 어댑터 등록 순서를 따른다(출력이 결정적). 알아볼 방법이 없는 종류는
    조용히 빠진다 — 훅이 그렇다.
    """
    from pouch.hosts.registry import toolbox_hosts

    if entry.surface == SURFACE_PLUGIN:
        return None  # 관측만 하는 자리 — 올리고 내릴 대상이 아니다

    found: list[str] = []
    for host in toolbox_hosts():
        if any(_sits_in(entry, box) for box in host.toolbox_paths()):
            found.append(host.name)
    return tuple(found)


def _sits_in(entry: ToolEntry, box: Toolbox) -> bool:
    """이 도구가 이 자리에 실제로 놓여 있나. 자리의 생김새(layout)가 보는 법을 정한다."""
    if not box.path.exists():
        return False  # 안 깔린 하네스는 흠이 아니다
    if box.layout == LAYOUT_SKILLS_ROOT:
        return entry.kind is ToolKind.SKILL and _has_skill(box.path, entry.id)
    if box.layout == LAYOUT_DOCS_FLAT:
        # 자리가 종류를 답한다 — `agents/`에 있으면 에이전트다(sweep과 같은 약속).
        return entry.kind is box.kind and _has_doc(box.path, entry.id)
    if box.layout == LAYOUT_FILE:
        return _registered_in_config(entry, box.path)
    return False  # 플러그인 캐시 등은 아직 알아보지 못한다


def _has_skill(root: Path, entry_id: str) -> bool:
    return (root / entry_id / _SKILL_FILENAME).is_file()


def _has_doc(root: Path, entry_id: str) -> bool:
    """평면 문서 한 장. 규칙은 `<분류>/<이름>.md`로 한 겹 접혀 있어 되편다."""
    return (root.joinpath(*unfold_rule_id(entry_id)).with_suffix(".md")).is_file()


def _registered_in_config(entry: ToolEntry, path: Path) -> bool:
    """설정 파일에 등록됐나 — MCP는 파일로 놓이지 않고 설정 안에 산다.

    깨진 설정은 "없음"으로 읽는다: 남의 파일이 망가졌다고 조회가 죽으면 안 된다.
    """
    if entry.ownership is not Ownership.LINKED:
        return False
    try:
        raw = path.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else {}
    except (OSError, json.JSONDecodeError):
        return False
    return entry.id in (data.get(_MCP_SERVERS_KEY) or {})
