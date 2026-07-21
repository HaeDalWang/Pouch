"""도구통 훑기 — 이미 깔린 것을 찾아 소스 대기실까지만 재운다.

배승도 락(2026-07-21): "도구통들만 지금 어디 있는지 검색을 안 해서 생긴 문제니까,
agent들마다 그러한 도구통들의 위치만 한 쑥 훑고 나서 대기실에만 올리면 그 뒤에는
evolve에서 처리될 테니까." 훑기는 찾아서 재우기만 한다 — 카탈로그 진입도, 표면
올리기도 하지 않는다(관문 (다) 불변식).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pouch.catalog.model import ToolKind
from pouch.catalog.store import CatalogStore
from pouch.catalog.sweep import sweep_toolboxes
from pouch.hosts.base import (
    LAYOUT_DOCS_FLAT,
    LAYOUT_FILE,
    LAYOUT_PLUGIN_CACHE,
    LAYOUT_SKILLS_ROOT,
    Toolbox,
)

_NOW = "2026-07-21T10:00:00"


@dataclass(frozen=True)
class FakeHost:
    """도구통만 가진 가짜 하네스 — 훑기는 어댑터 종류를 안 가린다."""

    name: str
    display_name: str
    boxes: tuple[Toolbox, ...]

    def toolbox_paths(self) -> tuple[Toolbox, ...]:
        return self.boxes


def _write_skill(root: Path, name: str, *, description: str = "설명") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n본문\n",
        encoding="utf-8",
    )
    return skill_dir


def _skills_host(root: Path, name: str = "fake") -> FakeHost:
    return FakeHost(
        name=name,
        display_name=name.title(),
        boxes=(Toolbox(path=root, layout=LAYOUT_SKILLS_ROOT),),
    )


def test_sweep_stages_already_installed_skills(tmp_path) -> None:
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "alpha")
    _write_skill(skills_root, "beta")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store, hosts=(_skills_host(skills_root),), synced_at=_NOW
    )

    assert set(report.staged) == {"alpha", "beta"}
    assert {entry.id for entry in source_store.list()} == {"alpha", "beta"}


def test_sweep_does_not_touch_the_catalog(tmp_path) -> None:
    """불변식 — 훑기는 대기실까지만. 카탈로그(진짜 주머니)는 그대로다."""
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "alpha")
    catalog_store = CatalogStore(catalog_dir=tmp_path / "catalog")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    sweep_toolboxes(
        source_store=source_store, hosts=(_skills_host(skills_root),), synced_at=_NOW
    )

    assert list(catalog_store.list()) == []


def test_sweep_is_idempotent(tmp_path) -> None:
    """두 번 훑어도 두 번 재우지 않는다 — 이미 있는 것은 already로 센다."""
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "alpha")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")
    hosts = (_skills_host(skills_root),)

    sweep_toolboxes(source_store=source_store, hosts=hosts, synced_at=_NOW)
    second = sweep_toolboxes(source_store=source_store, hosts=hosts, synced_at=_NOW)

    assert second.staged == ()
    assert second.already == 1


def test_sweep_skips_missing_toolbox_quietly(tmp_path) -> None:
    """도구통이 없는 하네스는 조용히 넘어간다 — 안 깔린 게 흠이 아니다."""
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")
    host = _skills_host(tmp_path / "없는곳")

    report = sweep_toolboxes(source_store=source_store, hosts=(host,), synced_at=_NOW)

    assert report.staged == ()
    assert report.skipped == ()


def test_one_broken_skill_does_not_block_the_rest(tmp_path) -> None:
    """인질 금지 — 깨진 조각 하나가 나머지를 막지 않고, 이유와 함께 보고된다."""
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "alpha")
    broken = skills_root / "broken"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text("이름도 frontmatter도 없음", encoding="utf-8")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store, hosts=(_skills_host(skills_root),), synced_at=_NOW
    )

    assert report.staged == ("alpha",)
    assert len(report.skipped) == 1
    assert "broken" in report.skipped[0]


def test_sweep_ignores_children_without_a_skill_file(tmp_path) -> None:
    """스킬 폴더 아래 잡동사니(캐시 등)는 후보가 아니다."""
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "alpha")
    (skills_root / "__pycache__").mkdir()
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store, hosts=(_skills_host(skills_root),), synced_at=_NOW
    )

    assert report.staged == ("alpha",)
    assert report.skipped == ()


def test_sweep_finds_plugins_nested_in_a_marketplace_cache(tmp_path) -> None:
    """실측 구조 <마켓>/<플러그인>/<버전>/ 을 파고들어 플러그인을 찾는다."""
    cache = tmp_path / "cache"
    plugin = cache / "some-market" / "some-plugin" / "1.0.0"
    _write_skill(plugin / "skills", "bundled-skill")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")
    host = FakeHost(
        name="fake",
        display_name="Fake",
        boxes=(Toolbox(path=cache, layout=LAYOUT_PLUGIN_CACHE),),
    )

    report = sweep_toolboxes(source_store=source_store, hosts=(host,), synced_at=_NOW)

    assert "bundled-skill" in report.staged


def test_sweep_reads_a_single_config_file(tmp_path) -> None:
    """파일 도구통(.mcp.json 등)은 그 파일 자체가 후보다."""
    mcp = tmp_path / ".mcp.json"
    mcp.write_text(
        '{"mcpServers": {"some-server": {"command": "run-it"}}}', encoding="utf-8"
    )
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")
    host = FakeHost(
        name="fake", display_name="Fake", boxes=(Toolbox(path=mcp, layout=LAYOUT_FILE),)
    )

    report = sweep_toolboxes(source_store=source_store, hosts=(host,), synced_at=_NOW)

    assert "some-server" in report.staged


def test_report_counts_per_host(tmp_path) -> None:
    """어느 하네스에서 몇 개가 나왔는지 — 사람이 읽을 보고용."""
    a_root = tmp_path / "a" / "skills"
    b_root = tmp_path / "b" / "skills"
    _write_skill(a_root, "alpha")
    _write_skill(b_root, "beta")
    _write_skill(b_root, "gamma")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store,
        hosts=(_skills_host(a_root, "a"), _skills_host(b_root, "b")),
        synced_at=_NOW,
    )

    assert report.per_host == {"a": 1, "b": 2}


def test_skip_reason_does_not_repeat_the_path(tmp_path) -> None:
    """importer가 이미 경로를 담은 메시지에 경로를 또 붙이지 않는다."""
    skills_root = tmp_path / "skills"
    broken = skills_root / "broken"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text("frontmatter 없음", encoding="utf-8")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store, hosts=(_skills_host(skills_root),), synced_at=_NOW
    )

    assert report.skipped[0].count(str(broken / "SKILL.md")) == 1


def test_sweep_command_stages_from_a_real_harness_dir(tmp_path, monkeypatch) -> None:
    """CLI 경로 — CLAUDE_CONFIG_DIR의 스킬 폴더를 훑어 소스에 재운다."""
    from typer.testing import CliRunner

    from pouch import paths
    from pouch.cli import app

    claude_home = tmp_path / "claude"
    _write_skill(claude_home / "skills", "swept-one")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    result = CliRunner().invoke(app, ["catalog", "sweep"])

    assert result.exit_code == 0
    staged = {e.id for e in CatalogStore(catalog_dir=paths.sources_dir()).list()}
    assert "swept-one" in staged
    # 불변식 — 표면(카탈로그)은 그대로다.
    assert list(CatalogStore().list()) == []


def _flat_docs_host(root: Path, kind: ToolKind, name: str = "fake") -> FakeHost:
    return FakeHost(
        name=name,
        display_name=name.title(),
        boxes=(Toolbox(path=root, layout=LAYOUT_DOCS_FLAT, kind=kind),),
    )


def _write_doc(root: Path, rel: str, *, name: str | None = None) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f"---\nname: {name}\ndescription: 설명\n---\n\n" if name else "---\ndescription: 설명\n---\n\n"
    path.write_text(head + "본문\n", encoding="utf-8")
    return path


def test_sweep_stages_flat_agent_files(tmp_path) -> None:
    """~/.claude/agents/ 처럼 평평하게 풀린 *.md 묶음을 담는다."""
    agents = tmp_path / "agents"
    _write_doc(agents, "reviewer.md", name="reviewer")
    _write_doc(agents, "planner.md", name="planner")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store,
        hosts=(_flat_docs_host(agents, ToolKind.AGENT),),
        synced_at=_NOW,
    )

    assert set(report.staged) == {"reviewer", "planner"}
    assert all(e.kind is ToolKind.AGENT for e in source_store.list())


def test_flat_commands_take_their_filename_as_id(tmp_path) -> None:
    """명령은 frontmatter name이 없어도 파일명이 정체다(런타임이 그렇게 부른다)."""
    commands = tmp_path / "commands"
    _write_doc(commands, "deploy.md")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store,
        hosts=(_flat_docs_host(commands, ToolKind.COMMAND),),
        synced_at=_NOW,
    )

    assert report.staged == ("deploy",)


def test_nested_rules_are_scoped_by_their_folder(tmp_path) -> None:
    """규칙은 같은 이름이 여러 폴더에 겹친다 — 부모 폴더로 스코프해 구분한다."""
    rules = tmp_path / "rules"
    _write_doc(rules, "coding-style.md")
    _write_doc(rules, "python/coding-style.md")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store,
        hosts=(_flat_docs_host(rules, ToolKind.RULE),),
        synced_at=_NOW,
    )

    assert set(report.staged) == {"rules__coding-style", "python__coding-style"}


def test_readme_is_not_a_tool(tmp_path) -> None:
    """폴더 안내문(README.md)은 도구가 아니다 — 플러그인 import와 같은 관례."""
    rules = tmp_path / "rules"
    _write_doc(rules, "README.md")
    _write_doc(rules, "testing.md")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store,
        hosts=(_flat_docs_host(rules, ToolKind.RULE),),
        synced_at=_NOW,
    )

    assert report.staged == ("rules__testing",)


def test_an_agent_without_a_name_is_skipped_not_guessed(tmp_path) -> None:
    """에이전트는 frontmatter name이 권위 — 없으면 파일명으로 추측하지 않고 건너뛴다."""
    agents = tmp_path / "agents"
    _write_doc(agents, "nameless.md")
    source_store = CatalogStore(catalog_dir=tmp_path / "sources")

    report = sweep_toolboxes(
        source_store=source_store,
        hosts=(_flat_docs_host(agents, ToolKind.AGENT),),
        synced_at=_NOW,
    )

    assert report.staged == ()
    assert len(report.skipped) == 1
