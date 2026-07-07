"""명령·에이전트 vendored-import 검증 — 커버리지 갭(kind 6종 중 막힌 것) 메우기.

스킬과 쌍둥이지만 정체(id) 해석이 갈린다:
  - agent : frontmatter `name`이 권위(스킬과 동일)
  - command: 파일명이 곧 정체(`santa-loop.md` → santa-loop). name 필드 없음.
    파일명은 추측이 아니라 런타임(슬래시 명령)이 쓰는 실제 id다.
본체(body)를 안 들이는 vendored 계약은 셋 다 동일하다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.importer import import_vendored_doc
from pouch.catalog.model import Ownership, ToolKind
from pouch.catalog.store import CatalogStore

_BODY_MARKER = "COMMAND_BODY_SHOULD_NOT_LEAK"

_AGENT_MD = """---
name: gan-planner
description: 한 줄 프롬프트를 제품 명세로 확장하는 플래너 에이전트
tools: ["Read", "Write"]
model: opus
---

# Planner

에이전트 본문 — 카탈로그에 새면 안 된다.
"""

_COMMAND_MD = f"""---
description: 두 리뷰어가 모두 통과해야 배포하는 수렴 루프
---

# Santa Loop

{_BODY_MARKER}
"""


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(catalog_dir=tmp_path / "catalog")


def _write(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_agent_import_uses_frontmatter_name(tmp_path: Path, store: CatalogStore) -> None:
    # Arrange — 에이전트는 name 필드가 권위 (파일명과 달라도 name을 쓴다)
    path = _write(tmp_path, "agents/planner-file.md", _AGENT_MD)

    # Act
    entry = import_vendored_doc(
        path, store, kind=ToolKind.AGENT, upstream=str(path), synced_at="2026-07-07"
    )

    # Assert
    assert entry.id == "gan-planner"  # 파일명(planner-file) 아니라 name
    assert entry.kind is ToolKind.AGENT
    assert entry.ownership is Ownership.VENDORED
    assert entry.body is None


def test_command_import_uses_filename_stem(tmp_path: Path, store: CatalogStore) -> None:
    # Arrange — 명령은 name 필드가 없다. 파일명이 곧 정체.
    path = _write(tmp_path, "commands/santa-loop.md", _COMMAND_MD)

    # Act
    entry = import_vendored_doc(
        path, store, kind=ToolKind.COMMAND, upstream=str(path), synced_at="2026-07-07"
    )

    # Assert
    assert entry.id == "santa-loop"  # 파일명 stem
    assert entry.kind is ToolKind.COMMAND
    assert entry.ownership is Ownership.VENDORED


def test_command_body_not_stored(tmp_path: Path, store: CatalogStore) -> None:
    # vendored 계약: 본문은 디스크 카탈로그에도 새지 않는다
    path = _write(tmp_path, "commands/santa-loop.md", _COMMAND_MD)

    import_vendored_doc(
        path, store, kind=ToolKind.COMMAND, upstream=str(path), synced_at="2026-07-07"
    )

    saved = (tmp_path / "catalog" / "santa-loop.md").read_text(encoding="utf-8")
    assert _BODY_MARKER not in saved


_RULE_MD = """---
paths:
  - "**/*.py"
---

# Python Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md).
"""


def test_rule_import_uses_parent_scoped_id(tmp_path: Path, store: CatalogStore) -> None:
    # 규칙은 name 필드가 없고 coding-style.md가 여러 언어에 겹친다.
    # 부모 디렉토리로 스코프한 flat-safe id로 충돌을 구조적으로 막는다.
    path = _write(tmp_path, "rules/python/coding-style.md", _RULE_MD)

    entry = import_vendored_doc(
        path, store, kind=ToolKind.RULE, upstream=str(path), synced_at="2026-07-07"
    )

    assert entry.id == "python__coding-style"  # <부모>__<stem>, 슬래시 없음
    assert entry.kind is ToolKind.RULE
    assert entry.ownership is Ownership.VENDORED


def test_rule_id_collision_resolved_by_parent(tmp_path: Path, store: CatalogStore) -> None:
    # 같은 stem(coding-style)이 부모가 다르면 다른 id — store에 둘 다 산다.
    p1 = _write(tmp_path, "rules/python/coding-style.md", _RULE_MD)
    p2 = _write(tmp_path, "rules/common/coding-style.md", _RULE_MD)

    e1 = import_vendored_doc(p1, store, kind=ToolKind.RULE, upstream=str(p1), synced_at="s")
    e2 = import_vendored_doc(p2, store, kind=ToolKind.RULE, upstream=str(p2), synced_at="s")

    assert e1.id == "python__coding-style"
    assert e2.id == "common__coding-style"
    assert store.get("python__coding-style") is not None
    assert store.get("common__coding-style") is not None


def test_command_reimport_preserves_overlay(tmp_path: Path, store: CatalogStore) -> None:
    # 재import 멱등 — overlay 보존(스킬과 같은 계약)
    from pouch.catalog.importer import apply_overlay
    from pouch.catalog.model import Overlay

    path = _write(tmp_path, "commands/santa-loop.md", _COMMAND_MD)
    import_vendored_doc(
        path, store, kind=ToolKind.COMMAND, upstream=str(path), synced_at="2026-07-07"
    )
    apply_overlay(store, "santa-loop", Overlay(notes="내 메모"))

    reimported = import_vendored_doc(
        path, store, kind=ToolKind.COMMAND, upstream=str(path), synced_at="2026-07-08"
    )

    assert reimported.overlay.notes == "내 메모"
    assert reimported.synced_at == "2026-07-08"
