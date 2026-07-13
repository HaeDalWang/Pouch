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


def test_evolve_drop_gates_boundaries_by_direction(tmp_path: Path, monkeypatch) -> None:
    # 도구를 내릴 때 그 도구 출신 boundary를 방향으로 가른다(P1 drop gate 배선):
    # allow는 함께 강등, deny는 잔존. 사람이 건 것은 무관하게 잔존.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))

    from pouch.catalog.install import install_entry
    from pouch.catalog.model import ToolEntry, ToolKind
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.state import record_installed
    from pouch.memory.model import (
        Direction,
        MemoryEntry,
        MemoryScope,
        MemoryState,
        MemoryType,
    )
    from pouch.memory.store import MemoryStore

    upstream = tmp_path / "up" / "aws-cdk" / "SKILL.md"
    upstream.parent.mkdir(parents=True)
    upstream.write_text("---\nname: aws-cdk\ndescription: d\n---\n\n본문", encoding="utf-8")
    entry = ToolEntry.vendored(
        id="aws-cdk", kind=ToolKind.SKILL, source="aws", title="aws-cdk",
        description="d", upstream=str(upstream), synced_at="2026-01-01",
    )
    store = CatalogStore()
    store.save(entry)
    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"
    install_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config)
    record_installed("aws-cdk", now="2026-01-01T00:00:00")  # 오래 전, 미사용 → drop 후보

    # 이 도구가 딸고 온 두 경계 + 사람이 건 하나
    mstore = MemoryStore()
    for name, direction, source in [
        ("cdk-dev-auto", Direction.ALLOW, "vendored:aws-cdk"),
        ("cdk-no-destroy", Direction.DENY, "vendored:aws-cdk"),
        ("my-own-rule", Direction.ALLOW, "user"),
    ]:
        mstore.save(
            MemoryEntry(
                name=name, description="d", body="b", type=MemoryType.BOUNDARY,
                scope=MemoryScope.GLOBAL, direction=direction, source=source,
            )
        )

    result = runner.invoke(
        app,
        ["evolve", "--yes", "--skills-dir", str(skills_dir), "--mcp-config", str(mcp_config)],
    )

    assert result.exit_code == 0, result.output
    # allow(도구 출신)는 함께 강등
    assert mstore.get("cdk-dev-auto", MemoryScope.GLOBAL).state is MemoryState.ARCHIVED
    # deny(도구 출신)는 잔존
    assert mstore.get("cdk-no-destroy", MemoryScope.GLOBAL).state is MemoryState.INDEXED
    # 사람이 건 것은 방향 무관하게 잔존
    assert mstore.get("my-own-rule", MemoryScope.GLOBAL).state is MemoryState.INDEXED


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


def _install_drop_candidate(tmp_path: Path) -> tuple[Path, Path]:
    """never-used + 유예 지난 vendored 도구를 심는다(drop 후보). skills·mcp 경로 반환."""
    from pouch.catalog.install import install_entry
    from pouch.catalog.model import ToolEntry, ToolKind
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.state import record_installed

    upstream = tmp_path / "up" / "aws-swift" / "SKILL.md"
    upstream.parent.mkdir(parents=True)
    upstream.write_text("---\nname: aws-swift\ndescription: d\n---\n\n본문", encoding="utf-8")
    entry = ToolEntry.vendored(
        id="aws-swift", kind=ToolKind.SKILL, source="aws", title="aws-swift",
        description="d", upstream=str(upstream), synced_at="2026-01-01",
    )
    CatalogStore().save(entry)
    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"
    install_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config)
    record_installed("aws-swift", now="2026-01-01T00:00:00")  # 오래 전, 미사용
    return skills_dir, mcp_config


def test_contract7_dry_run_shows_undo_but_changes_nothing(tmp_path: Path, monkeypatch) -> None:
    # 조각 6: '정리하자' 다리 = 읽기전용 목록. preview의 되돌림을 보여주되 실행 안 함.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    skills_dir, mcp_config = _install_drop_candidate(tmp_path)

    # 입력을 주지 않는다 — dry-run은 물음(confirm) 없이도 끝나야 한다(비대화형 안전)
    result = runner.invoke(
        app,
        ["evolve", "--dry-run", "--skills-dir", str(skills_dir), "--mcp-config", str(mcp_config)],
    )

    assert result.exit_code == 0, result.output
    assert "aws-swift" in result.output
    # 되돌리는 정확한 명령(preview 단일 출처)이 목록에 함께 나온다
    assert "pouch catalog install aws-swift" in result.output
    # ★ 아무것도 안 내려감 — 표면 그대로(볼게, 해 아님)
    assert (skills_dir / "aws-swift" / "SKILL.md").exists()


def test_contract7d_dry_run_advises_on_plugin_usage(tmp_path: Path, monkeypatch) -> None:
    # (A→B) 조각 1 배선: plugin 관측 사용이 조언으로 뜬다(pouch가 안 내림, 안내만).
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    from datetime import datetime, timedelta

    from pouch.catalog.model import SURFACE_PLUGIN, ToolEntry, ToolKind
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.usage_log import UsageEvent, append_event

    store = CatalogStore()
    # ECC가 관리하는 plugin 도구(관측 전용) — alias로 런타임 사용명과 이어짐
    store.save(
        ToolEntry.linked(
            id="context7", kind=ToolKind.MCP, source="ecc", title="context7",
            description="라이브러리 문서", recipe={}, surface=SURFACE_PLUGIN,
            aliases=("plugin_everything-claude-code_context7",),
        )
    )
    # 최근 자주 씀 → 강화 조언
    fresh = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    for _ in range(9):
        append_event(UsageEvent(entry_id="plugin_everything-claude-code_context7", ts=fresh))

    result = runner.invoke(app, ["evolve", "--dry-run"])

    assert result.exit_code == 0, result.output
    # plugin 도구가 조언으로 인식됨(관측만 죽은 줄이 아니라)
    assert "context7" in result.output
    # pouch가 표면을 강제로 안 바꾼다는 게 드러나야(조언·안내 어조)
    assert "잘 쓰" in result.output or "강화" in result.output or "자주" in result.output


def test_contract7c_dry_run_shows_similar_for_repeated_anchor(tmp_path: Path, monkeypatch) -> None:
    # 조각 3('이거 써봐'): reattach 앵커가 뜰 때 같은 태그의 비슷한 후보도 함께.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    from datetime import datetime, timedelta

    from pouch.catalog.install import install_entry
    from pouch.catalog.model import Overlay, ToolEntry, ToolKind
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.orchestrate import apply_drop
    from pouch.evolution.usage_log import UsageEvent, append_event

    store = CatalogStore()
    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"

    # 앵커(terraform)와 비슷한 후보(pulumi)를 같은 태그로 카탈로그에 담는다
    for tool_id in ("terraform", "pulumi"):
        up = tmp_path / "up" / tool_id / "SKILL.md"
        up.parent.mkdir(parents=True)
        up.write_text(f"---\nname: {tool_id}\ndescription: d\n---\n\n본문", encoding="utf-8")
        entry = ToolEntry.vendored(
            id=tool_id, kind=ToolKind.SKILL, source="s", title=tool_id,
            description=f"{tool_id} 설명", upstream=str(up), synced_at="2026-01-01",
            overlay=Overlay(tags=("iac", "cloud")),
        )
        store.save(entry)

    # terraform만 설치했다 내리고 최근 다시 씀 → reattach 앵커. pulumi는 카탈로그만(비슷).
    install_entry(store.get("terraform"), skills_dir=skills_dir, mcp_config_path=mcp_config)
    apply_drop("terraform", store=store, skills_dir=skills_dir, mcp_config_path=mcp_config)
    fresh = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    append_event(UsageEvent(entry_id="terraform", ts=fresh))

    result = runner.invoke(
        app,
        ["evolve", "--dry-run", "--skills-dir", str(skills_dir), "--mcp-config", str(mcp_config)],
    )

    assert result.exit_code == 0, result.output
    # 앵커 곁에 비슷한 후보(pulumi)가 함께 뜬다 — "이거 써봐"
    assert "pulumi" in result.output
    assert "비슷" in result.output


def test_contract7b_dry_run_does_not_compact_log(tmp_path: Path, monkeypatch) -> None:
    # dry-run은 읽기전용 — 오래된 사용 로그도 접지 않는다(mutation 금지)
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    from pouch.evolution.usage_log import UsageEvent, append_event, read_events

    log = tmp_path / "usage.jsonl"
    # compaction 경계(180일)보다 훨씬 오래된 이벤트 — 평소 evolve면 접힐 것
    append_event(UsageEvent(entry_id="old-tool", ts="2020-01-01T00:00:00"), log_path=log)

    result = runner.invoke(app, ["evolve", "--dry-run"])

    assert result.exit_code == 0
    # 로그가 그대로 남아있다(접히지 않음)
    events = read_events(log_path=log)
    assert len(events) == 1 and events[0].entry_id == "old-tool"


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
