"""내리기도 제 서랍을 본다 — 올리기(④ 종류별 제 서랍)의 빠진 거울상.

2026-07-22 발견: 규칙 서랍을 달다가 드러났다. 올리기는 종류별 서랍으로 갔는데
(2026-07-21) 내리기는 여전히 스킬 서랍만 뒤졌다 — 에이전트·명령을 내려도 파일이
표면에 그대로 남아 계속 읽혔다. "내렸습니다"가 거짓말이 되던 자리다.

"떨어진다 ≠ 삭제된다"는 **카탈로그·개인화**가 남는다는 뜻이지, 표면 파일이
남는다는 뜻이 아니다.
"""

from __future__ import annotations

from pouch.catalog.install import install_doc_file
from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.uninstall import uninstall_entry


def _doc(kind: ToolKind, entry_id: str) -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id, kind=kind, source="test",
        title=entry_id, description="설명", body="본문",
    )


def _drop(entry: ToolEntry, base) -> None:
    uninstall_entry(
        entry,
        skills_dir=base / "skills",
        mcp_config_path=base / ".mcp.json",
        surface_base=base,
    )


def test_dropping_an_agent_removes_it_from_the_agents_drawer(tmp_path) -> None:
    entry = _doc(ToolKind.AGENT, "reviewer")
    written = install_doc_file(entry, base=tmp_path)

    _drop(entry, tmp_path)

    assert not written.exists()


def test_dropping_a_command_removes_it_from_the_commands_drawer(tmp_path) -> None:
    entry = _doc(ToolKind.COMMAND, "deploy")
    written = install_doc_file(entry, base=tmp_path)

    _drop(entry, tmp_path)

    assert not written.exists()


def test_dropping_a_rule_removes_it_from_its_original_folder(tmp_path) -> None:
    entry = _doc(ToolKind.RULE, "python__coding-style")
    written = install_doc_file(entry, base=tmp_path)

    _drop(entry, tmp_path)

    assert not written.exists()


def test_dropping_a_rule_leaves_its_neighbours_alone(tmp_path) -> None:
    """같은 묶음의 다른 규칙까지 쓸어가지 않는다 — 폴더째 지우면 나던 사고."""
    dropped = _doc(ToolKind.RULE, "python__coding-style")
    kept = _doc(ToolKind.RULE, "python__testing")
    install_doc_file(dropped, base=tmp_path)
    kept_path = install_doc_file(kept, base=tmp_path)

    _drop(dropped, tmp_path)

    assert kept_path.exists()


def test_dropping_a_doc_that_was_never_installed_is_quiet(tmp_path) -> None:
    """멱등 — 없는 걸 내려도 안 죽는다."""
    _drop(_doc(ToolKind.AGENT, "ghost"), tmp_path)


def test_dropping_a_skill_still_uses_the_skills_drawer(tmp_path) -> None:
    """기존 계약 회귀 방어 — 스킬은 폴더째 사라진다."""
    entry = _doc(ToolKind.SKILL, "my-skill")
    written = install_doc_file(entry, base=tmp_path)

    _drop(entry, tmp_path)

    assert not written.exists()
    assert not (tmp_path / "skills" / "my-skill").exists()
