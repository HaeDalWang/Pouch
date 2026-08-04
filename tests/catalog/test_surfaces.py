"""표면 조회 검증 — "이 도구가 지금 어느 하네스에 올라가 있나".

  ① 스킬은 `<skills>/<id>/SKILL.md`가 있으면 그 표면에 올라간 것
  ② 평면 문서(agent·command·rule)는 자리가 종류를 답한다 — 종류가 다르면 아니다
  ③ MCP(linked)는 파일이 아니라 설정 안에 산다 — 설정을 읽어야 안다
  ④ 여러 표면에 있으면 여럿 다 돌려준다 (하네스 사이 다리의 재료)
  ⑤ 저장하지 않고 매번 실측 — 사용자가 파일을 직접 지워도 어긋나지 않는다
  ⑥ 못 보는 종류는 조용히 빈 값 — 모르는 걸 있다고 하지 않는다
  ⑦ 플러그인이 관리하는 항목은 **None(판단 불가)** — "없음"과 "모름"은 다르다
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pouch.catalog.model import SURFACE_PLUGIN, Ownership, ToolEntry, ToolKind
from pouch.catalog.surfaces import installed_surfaces


@pytest.fixture
def surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Claude·Codex 홈을 임시 경로로 격리한다."""
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir()
    codex.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    monkeypatch.setenv("CODEX_HOME", str(codex))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _skill(entry_id: str) -> ToolEntry:
    return ToolEntry(
        id=entry_id, title=entry_id, description="d",
        kind=ToolKind.SKILL, ownership=Ownership.OWNED, source="test",
    )


def _put_skill(root: Path, entry_id: str) -> None:
    d = root / "skills" / entry_id
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# skill", encoding="utf-8")


def test_contract1_skill_found_on_claude(surfaces: Path) -> None:
    _put_skill(surfaces / "claude", "aws-iam")

    assert installed_surfaces(_skill("aws-iam")) == ("claude",)


def test_contract1_absent_skill_is_nowhere(surfaces: Path) -> None:
    assert installed_surfaces(_skill("never-installed")) == ()


def test_contract2_doc_kind_must_match_the_drawer(surfaces: Path) -> None:
    """`agents/`에 놓인 파일은 에이전트다 — 같은 이름의 명령을 찾으면 안 된다."""
    agents = surfaces / "claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "reviewer.md").write_text("# agent", encoding="utf-8")

    as_agent = ToolEntry(
        id="reviewer", title="reviewer", description="d",
        kind=ToolKind.AGENT, ownership=Ownership.VENDORED, source="test",
    )
    as_command = ToolEntry(
        id="reviewer", title="reviewer", description="d",
        kind=ToolKind.COMMAND, ownership=Ownership.VENDORED, source="test",
    )

    assert installed_surfaces(as_agent) == ("claude",)
    assert installed_surfaces(as_command) == ()  # 명령 서랍엔 없다


def test_contract3_linked_mcp_read_from_config(surfaces: Path) -> None:
    """MCP는 파일로 놓이지 않는다 — 설정 안에 등록돼 있어야 올라간 것."""
    (surfaces / "claude" / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"code-review-graph": {"command": "uvx"}}}),
        encoding="utf-8",
    )
    entry = ToolEntry(
        id="code-review-graph", title="crg", description="d",
        kind=ToolKind.MCP, ownership=Ownership.LINKED, source="test",
    )

    assert installed_surfaces(entry) == ("claude",)


def test_contract4_reports_every_surface_it_sits_on(surfaces: Path) -> None:
    """양쪽에 있으면 둘 다. 이게 '여긴 있고 저긴 없네'의 재료다."""
    _put_skill(surfaces / "claude", "shared-skill")
    _put_skill(surfaces / "codex", "shared-skill")

    assert installed_surfaces(_skill("shared-skill")) == ("claude", "codex")


def test_contract4_finds_a_skill_only_on_codex(surfaces: Path) -> None:
    _put_skill(surfaces / "codex", "codex-only")

    assert installed_surfaces(_skill("codex-only")) == ("codex",)


def test_contract5_reflects_manual_deletion(surfaces: Path) -> None:
    """사용자가 직접 지우면 즉시 반영된다 — 저장한 값이 아니라 실측이라서."""
    _put_skill(surfaces / "claude", "temp")
    assert installed_surfaces(_skill("temp")) == ("claude",)

    import shutil

    shutil.rmtree(surfaces / "claude" / "skills" / "temp")

    assert installed_surfaces(_skill("temp")) == ()


def test_contract6_unknown_kind_reports_nothing(surfaces: Path) -> None:
    """훅은 표면에서 알아볼 방법이 아직 없다 — 없다고 하지 말고 모른다고 한다."""
    hook = ToolEntry(
        id="some-hook", title="h", description="d",
        kind=ToolKind.HOOK, ownership=Ownership.VENDORED, source="test",
    )

    assert installed_surfaces(hook) == ()


def test_contract7_plugin_managed_is_unknown_not_absent(surfaces: Path) -> None:
    """플러그인이 관리하면 판단 불가(None)다 — 빈 튜플(없음)로 답하면 거짓말이 된다.

    실측 근거(2026-08-04): aws-mcp는 매일 쓰이는데도 pouch가 보는 자리엔 없다.
    플러그인이 자기 방식으로 등록하기 때문이다. 이걸 "없음"으로 답하면 "Codex에도
    올려볼까요?" 같은 헛제안이나 drop 후보로 이어진다.
    """
    plugin_mcp = ToolEntry(
        id="aws-mcp", title="aws", description="d",
        kind=ToolKind.MCP, ownership=Ownership.LINKED, source="test",
        surface=SURFACE_PLUGIN,
    )

    assert installed_surfaces(plugin_mcp) is None


def test_contract7_plugin_verdict_wins_over_a_found_file(surfaces: Path) -> None:
    """플러그인이 풀어놓은 파일이 우리 자리에 보여도 판단 불가다.

    거기 있는 건 사실이지만 **pouch가 놓은 게 아니라** 올리고 내릴 대상이 아니다.
    """
    _put_skill(surfaces / "claude", "plugin-skill")
    entry = ToolEntry(
        id="plugin-skill", title="p", description="d",
        kind=ToolKind.SKILL, ownership=Ownership.VENDORED, source="test",
        surface=SURFACE_PLUGIN,
    )

    assert installed_surfaces(entry) is None
