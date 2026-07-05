"""`pouch evolve` CLI 계약 검증 — 사용 로깅 + drop 제안/적용.

  ① evolve log: stdin의 PostToolUse 페이로드 → usage.jsonl append
  ② evolve log: 깨진/추적무관 stdin → 조용히 exit 0 (hook 절대 안 죽음)
  ③ evolve(후보 없음): "정리할 것 없음" 안내, 아무것도 안 내림
  ④ evolve --yes: 후보를 표면에서 내리고 카탈로그는 보존
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pouch.cli import app

runner = CliRunner()


def test_contract1_log_appends_skill_usage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    payload = json.dumps({"tool_name": "Skill", "tool_input": {"skill": "aws-iam"}})

    result = runner.invoke(app, ["evolve", "log"], input=payload)

    assert result.exit_code == 0
    from pouch.evolution.usage_log import read_events

    events = read_events(log_path=tmp_path / "usage.jsonl")
    assert len(events) == 1
    assert events[0].entry_id == "aws-iam"


def test_contract2_log_survives_broken_stdin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))

    result = runner.invoke(app, ["evolve", "log"], input="{not json")

    assert result.exit_code == 0  # hook은 절대 안 죽는다
    assert not (tmp_path / "usage.jsonl").exists()


def test_contract2_log_ignores_untracked_tool(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})

    result = runner.invoke(app, ["evolve", "log"], input=payload)

    assert result.exit_code == 0
    assert not (tmp_path / "usage.jsonl").exists()


def test_contract3_evolve_no_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))

    result = runner.invoke(app, ["evolve"])

    assert result.exit_code == 0
    assert "정리할" in result.output or "없" in result.output


def test_contract4_evolve_yes_drops_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))

    # never-used + 유예 지난 vendored 도구를 심는다
    from pouch.catalog.install import install_entry
    from pouch.catalog.model import Overlay, ToolEntry, ToolKind
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.state import record_installed

    upstream = tmp_path / "up" / "aws-swift" / "SKILL.md"
    upstream.parent.mkdir(parents=True)
    upstream.write_text("---\nname: aws-swift\ndescription: d\n---\n\n# s\n\n본문", encoding="utf-8")
    entry = ToolEntry.vendored(
        id="aws-swift", kind=ToolKind.SKILL, source="aws", title="aws-swift",
        description="d", upstream=str(upstream), synced_at="2026-01-01",
        overlay=Overlay(boundaries=("prod-gate",)),
    )
    store = CatalogStore()
    store.save(entry)
    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"
    install_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config)
    record_installed("aws-swift", now="2026-01-01T00:00:00")  # 오래 전 설치, 미사용

    result = runner.invoke(
        app,
        ["evolve", "--yes", "--skills-dir", str(skills_dir), "--mcp-config", str(mcp_config)],
    )

    assert result.exit_code == 0
    assert "aws-swift" in result.output
    # 표면에서 내려감
    assert not (skills_dir / "aws-swift" / "SKILL.md").exists()
    # ★ 카탈로그 엔트리 + overlay 생존
    survived = store.get("aws-swift")
    assert survived is not None and survived.overlay.boundaries == ("prod-gate",)


def test_contract5_evolve_shows_pending_and_promotes_on_yes(tmp_path: Path, monkeypatch) -> None:
    # 기억의 들어오는 문 — pending 스테이징을 evolve가 같은 화면에 보여주고 확인시킨다.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    from pouch.memory.model import MemoryScope
    from pouch.memory.store import MemoryStore

    runner.invoke(
        app,
        ["memory", "add", "-n", "sprint", "-d", "d", "-b", "b",
         "-t", "project", "-s", "global", "--pending"],
    )

    result = runner.invoke(app, ["evolve", "--yes"])

    assert result.exit_code == 0
    assert "sprint" in result.output
    stored = MemoryStore().get("sprint", MemoryScope.GLOBAL)
    assert stored is not None and stored.state.value == "indexed"


def test_contract6_evolve_shows_hygiene_and_demotes_on_yes(tmp_path: Path, monkeypatch) -> None:
    # 기억의 나가는 문 — 죽은 reference를 evolve가 강등 제안하고 확인 시 내린다.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    from pouch.memory.model import MemoryScope
    from pouch.memory.store import MemoryStore

    runner.invoke(
        app,
        ["memory", "add", "-n", "dead-dash", "-d", "d", "-b", "/no/such/path.md",
         "-t", "reference", "-s", "global"],
    )

    result = runner.invoke(app, ["evolve", "--yes"])

    assert result.exit_code == 0
    assert "dead-dash" in result.output
    stored = MemoryStore().get("dead-dash", MemoryScope.GLOBAL)
    assert stored is not None and stored.state.value == "archived"
