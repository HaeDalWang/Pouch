"""종류별 서랍 — 올릴 때 제 자리에 놓는다.

배승도 락(2026-07-21): "도구통에 담는 것까지는 맞는데, 도구통 자체를 서랍에
분류하는데 지금 잘못 놓을 뻔했다. 어차피 claude에서 잘 나눠놔서 그대로
재사용하면 된다는 거잖아."

전에는 훅·MCP를 뺀 나머지가 전부 `skills/<id>/SKILL.md`로 갔다 — 에이전트도,
명령도 스킬인 척 쓰였다. 하네스가 이미 나눠둔 자리를 그대로 쓴다. 서랍이
없는 종류는 엉뚱한 데 놓지 않고 정직하게 거절한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.catalog.install import install_doc_file, target_path_for
from pouch.catalog.model import ToolEntry, ToolKind


def _owned(kind: ToolKind, entry_id: str = "thing") -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id, kind=kind, source="test", title=entry_id,
        description="설명", body="본문",
    )


def test_skill_keeps_its_folder_shape(tmp_path) -> None:
    """스킬만 폴더를 만들어 그 안에 SKILL.md — 기존 동작 그대로."""
    assert target_path_for(
        _owned(ToolKind.SKILL, "my-skill"), base=tmp_path
    ) == tmp_path / "skills" / "my-skill" / "SKILL.md"


@pytest.mark.parametrize(
    ("kind", "drawer"),
    [(ToolKind.AGENT, "agents"), (ToolKind.COMMAND, "commands")],
)
def test_agents_and_commands_go_flat_into_their_own_drawer(
    kind: ToolKind, drawer: str, tmp_path
) -> None:
    """에이전트·명령은 평평한 파일 하나 — 하네스가 그렇게 읽는다."""
    assert target_path_for(_owned(kind, "helper"), base=tmp_path) == (
        tmp_path / drawer / "helper.md"
    )


def test_a_kind_without_a_drawer_is_refused(tmp_path) -> None:
    """서랍이 없으면 엉뚱한 데 놓지 않고 거절한다(조용히 스킬 취급하지 않는다)."""
    with pytest.raises(ValueError, match="올릴 자리"):
        target_path_for(_owned(ToolKind.MCP, "some-server"), base=tmp_path)


def test_installing_an_agent_writes_to_the_agents_drawer(tmp_path) -> None:
    written = install_doc_file(_owned(ToolKind.AGENT, "reviewer"), base=tmp_path)

    assert written == tmp_path / "agents" / "reviewer.md"
    assert "본문" in written.read_text(encoding="utf-8")


def test_an_installed_agent_is_not_left_in_the_skills_drawer(tmp_path) -> None:
    """회귀 방어 — 이게 바로 고친 결함이다."""
    install_doc_file(_owned(ToolKind.AGENT, "reviewer"), base=tmp_path)

    assert not (tmp_path / "skills" / "reviewer").exists()


def test_installed_doc_keeps_frontmatter_so_the_harness_can_read_it(tmp_path) -> None:
    import frontmatter

    written = install_doc_file(_owned(ToolKind.AGENT, "reviewer"), base=tmp_path)

    meta = frontmatter.loads(written.read_text(encoding="utf-8"))
    assert meta["name"] == "reviewer"
    assert meta["description"] == "설명"


def test_vendored_doc_is_read_back_from_upstream(tmp_path) -> None:
    upstream = tmp_path / "src" / "AGENT.md"
    upstream.parent.mkdir(parents=True)
    upstream.write_text("---\nname: up\n---\n\n원본 본문\n", encoding="utf-8")
    entry = ToolEntry.vendored(
        id="up", kind=ToolKind.AGENT, source="test", title="up",
        description="설명", upstream=str(upstream), synced_at="2026-07-21T10:00:00",
    )

    written = install_doc_file(entry, base=tmp_path / "out")

    assert "원본 본문" in written.read_text(encoding="utf-8")
