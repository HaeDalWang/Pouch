"""세트 내보내기 — 표면을 세트로 굳히기 + apply 왕복."""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.importer import import_vendored_skill
from pouch.catalog.model import SURFACE_PLUGIN, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.sets.apply import apply_set
from pouch.sets.export import build_export_set


def _skill_md(path: Path, name: str, description: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\nbody", encoding="utf-8")
    return path


# ── 순수 판정 ────────────────────────────────────────────────────────────


def test_homeifies_upstream_for_portability() -> None:
    entry = ToolEntry.vendored(
        id="s", kind=ToolKind.SKILL, source="t", title="s", description="d",
        upstream="/home/me/.claude/plugins/ecc/skills/s/SKILL.md",
    )
    result = build_export_set("set", [entry], {"s"}, home=Path("/home/me"))
    assert result.starter.items[0].source == "~/.claude/plugins/ecc/skills/s/SKILL.md"
    assert result.starter.items[0].install == ("s",)


def test_skips_owned_mcp_and_plugin_surface_with_reasons() -> None:
    owned = ToolEntry.owned(
        id="mine", kind=ToolKind.SKILL, source="t", title="mine", description="d", body="b",
    )
    mcp = ToolEntry.linked(
        id="exa", kind=ToolKind.MCP, source="t", title="exa", description="d",
        recipe={"command": "x"},  # upstream 없음
    )
    plugin = ToolEntry.linked(
        id="ecc-skill", kind=ToolKind.SKILL, source="t", title="ecc-skill", description="d",
        recipe={}, surface=SURFACE_PLUGIN,
    )
    result = build_export_set(
        "set", [owned, mcp, plugin], {"mine", "exa", "ecc-skill"}, home=Path("/h"),
    )
    assert result.starter.items == ()  # 담을 게 없다
    reasons = "\n".join(result.skipped)
    assert "mine" in reasons and "몸을 직접 소유" in reasons
    assert "exa" in reasons and "연결형" in reasons
    assert "ecc-skill" in reasons and "플러그인" in reasons


def test_match_tokens_derived_from_exported_tools() -> None:
    entry = ToolEntry.vendored(
        id="tf", kind=ToolKind.SKILL, source="t", title="tf", description="Terraform on AWS",
        upstream="/h/tf/SKILL.md",
    )
    result = build_export_set("set", [entry], {"tf"}, home=Path("/h"))
    assert "terraform" in result.starter.match_tokens
    assert "aws" in result.starter.match_tokens


def test_only_active_surface_is_exported() -> None:
    a = ToolEntry.vendored(
        id="a", kind=ToolKind.SKILL, source="t", title="a", description="d", upstream="/h/a/SKILL.md",
    )
    b = ToolEntry.vendored(
        id="b", kind=ToolKind.SKILL, source="t", title="b", description="d", upstream="/h/b/SKILL.md",
    )
    # b는 카탈로그엔 있지만 표면(active)이 아님 → 세트에 안 담긴다.
    result = build_export_set("set", [a, b], {"a"}, home=Path("/h"))
    assert [item.install[0] for item in result.starter.items] == ["a"]


# ── apply 왕복 (실물 파일) ────────────────────────────────────────────────


def test_export_then_apply_round_trips(tmp_path: Path) -> None:
    # 단독 SKILL.md를 vendored로 들여 표면에 올린 상태를 가정.
    skill_md = _skill_md(tmp_path / "src" / "SKILL.md", "my-skill", "Deploy helper")
    store1 = CatalogStore(catalog_dir=tmp_path / "catalog1")
    entry = import_vendored_skill(skill_md, store1, upstream=str(skill_md), synced_at="2026-07-16T00:00:00")

    # 홈 밖 경로라 절대경로가 그대로 남는다 → 실제 파일을 다시 가리킨다.
    result = build_export_set(
        "myset", list(store1.list()), {entry.id}, home=Path("/no-such-home"),
    )
    assert result.starter.items[0].source == str(skill_md)

    # 내보낸 세트를 빈 store에 적용 → 도구가 되살아나 표면에 올라온다.
    store2 = CatalogStore(catalog_dir=tmp_path / "catalog2")
    report = apply_set(
        result.starter, store2,
        skills_dir=tmp_path / "surface2",
        mcp_config_path=tmp_path / ".mcp.json",
        settings_path=tmp_path / "settings.json",
        state_path=tmp_path / "state2.json",
        synced_at="2026-07-16T00:00:00",
    )
    assert entry.id in report.installed
    assert store2.get(entry.id) is not None
    assert (tmp_path / "surface2" / entry.id / "SKILL.md").exists()
