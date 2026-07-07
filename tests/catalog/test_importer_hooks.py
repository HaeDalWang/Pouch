"""훅 가져오기 계약 — hooks.json을 낱개 조리법으로 분해해 담는다.

훅은 "읽는 지식"이 아니라 "실행 배선"이다: {언제(사건), 무엇에(대상), 무슨 명령}.
도구연결(mcp)과 같은 결로 linked + 조리법(recipe)으로 담는다.

  ① hooks.json의 그룹 하나 = 카탈로그 항목 하나 (kind=hook, linked)
  ② recipe에 사건·대상·명령·설명이 그대로 담긴다 (설치 때 원문 표시의 근거)
  ③ 그룹 id를 정체로 쓰되 파일명에 못 쓰는 글자(:)는 -로 바꾼다
  ④ id가 없는 그룹은 사건+대상으로 결정적 id를 만든다 (훅은 사용 기록과
     이름을 맞출 필요가 없어 합성 id가 안전하다 — 스킬의 name 요구와 다른 이유)
  ⑤ 대상(matcher)이 없는 사건(SessionStart 등)도 담긴다
  ⑥ 플러그인에서 온 훅은 surface=plugin — 플러그인이 이미 실행 중이라
     pouch가 또 배선하면 이중 실행이 된다 (mcp와 같은 취급)
  ⑦ import_plugin이 hooks/hooks.json을 자동으로 집어간다
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch.catalog.importer import import_hooks, import_plugin
from pouch.catalog.model import SURFACE_PLUGIN, Ownership, ToolKind
from pouch.catalog.store import CatalogStore

_HOOKS_JSON = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "node check.js"}],
                "description": "Bash 실행 전 점검",
                "id": "pre:bash:check",
            },
            {
                "matcher": "Write",
                "hooks": [{"type": "command", "command": "node warn.js"}],
                # id 없음 — 결정적 fallback을 검증
            },
        ],
        "SessionStart": [
            {
                # matcher 없음 — 사건 전체에 걸리는 훅
                "hooks": [{"type": "command", "command": "node greet.js"}],
                "id": "session:greet",
            }
        ],
    }
}


def _write_hooks_json(directory: Path) -> Path:
    path = directory / "hooks.json"
    path.write_text(json.dumps(_HOOKS_JSON), encoding="utf-8")
    return path


def test_contract1_one_group_becomes_one_linked_hook_entry(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    entries = import_hooks(_write_hooks_json(tmp_path), store, source="ecc")

    assert len(entries) == 3
    assert all(e.kind is ToolKind.HOOK for e in entries)
    assert all(e.ownership is Ownership.LINKED for e in entries)
    # store에도 저장됐다
    assert store.get("pre-bash-check") is not None


def test_contract2_recipe_holds_event_matcher_commands(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    entries = import_hooks(_write_hooks_json(tmp_path), store, source="ecc")

    bash_check = next(e for e in entries if e.id == "pre-bash-check")
    assert bash_check.recipe["event"] == "PreToolUse"
    assert bash_check.recipe["matcher"] == "Bash"
    assert bash_check.recipe["hooks"][0]["command"] == "node check.js"
    assert bash_check.description == "Bash 실행 전 점검"


def test_contract3_group_id_sanitized_for_filenames(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    entries = import_hooks(_write_hooks_json(tmp_path), store, source="ecc")

    ids = {e.id for e in entries}
    assert "pre-bash-check" in ids  # "pre:bash:check" → ":"가 "-"로
    assert not any(":" in e.id for e in entries)


def test_contract4_missing_id_gets_deterministic_fallback(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    first = import_hooks(_write_hooks_json(tmp_path), store, source="ecc")
    second = import_hooks(_write_hooks_json(tmp_path), store, source="ecc")

    no_id = [e for e in first if "write" in e.id.lower()]
    assert len(no_id) == 1  # 사건+대상으로 만든 id가 존재
    # 결정적: 다시 들여도 같은 id (멱등 — 중복 항목이 안 생긴다)
    assert {e.id for e in first} == {e.id for e in second}


def test_contract5_event_without_matcher(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    entries = import_hooks(_write_hooks_json(tmp_path), store, source="ecc")

    greet = next(e for e in entries if e.id == "session-greet")
    assert greet.recipe["event"] == "SessionStart"
    assert "matcher" not in greet.recipe or not greet.recipe.get("matcher")


def test_contract6_plugin_hooks_are_plugin_surfaced(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    entries = import_hooks(
        _write_hooks_json(tmp_path), store, source="ecc", plugin_name="ecc"
    )

    assert all(e.surface == SURFACE_PLUGIN for e in entries)


def test_contract7_import_plugin_picks_up_hooks_json(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin"
    (plugin / "skills" / "demo").mkdir(parents=True)
    (plugin / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\nbody", encoding="utf-8"
    )
    (plugin / "hooks").mkdir()
    _write_hooks_json(plugin / "hooks")
    manifest_dir = plugin / ".claude-plugin"
    manifest_dir.mkdir()
    (manifest_dir / "plugin.json").write_text('{"name": "ecc"}', encoding="utf-8")

    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    result = import_plugin(plugin, store, synced_at="2026-07-07T00:00:00", source="ecc")

    hooks = [e for e in result.entries if e.kind is ToolKind.HOOK]
    assert len(hooks) == 3
    # 플러그인 경유라 표면은 플러그인 관리(관측만)
    assert all(e.surface == SURFACE_PLUGIN for e in hooks)
