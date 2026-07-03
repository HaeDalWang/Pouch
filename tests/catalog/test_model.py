"""ToolEntry 모델 — ownership 3값 직렬화/팩토리 검증."""

from __future__ import annotations

from pouch.catalog.model import Overlay, Ownership, ToolEntry, ToolKind


def test_owned_factory_sets_ownership_and_body() -> None:
    # Act
    entry = ToolEntry.owned(
        id="legacy-skill",
        kind=ToolKind.SKILL,
        source="ecc",
        title="입양한 스킬",
        description="upstream 없는 ECC 스킬",
        body="# 본문\n자유롭게 깎는다.",
        tags=("role:dev",),
    )

    # Assert
    assert entry.ownership is Ownership.OWNED
    assert entry.body is not None
    assert entry.upstream is None


def test_vendored_factory_tracks_upstream_without_body() -> None:
    # Act
    entry = ToolEntry.vendored(
        id="aws-iam",
        kind=ToolKind.SKILL,
        source="aws",
        title="AWS IAM",
        description="검증된 최신 IAM 절차",
        upstream="aws/agent-toolkit-for-aws/skills/aws-iam",
        tags=("vendor:aws",),
        overlay=Overlay(boundaries=("prod-gate",), notes="prod는 확인"),
    )

    # Assert — body는 들지 않는다(upstream sync 참조)
    assert entry.ownership is Ownership.VENDORED
    assert entry.body is None
    assert entry.upstream.endswith("aws-iam")
    assert entry.overlay is not None
    assert entry.overlay.boundaries == ("prod-gate",)


def test_linked_factory_holds_recipe_and_region() -> None:
    # Act
    entry = ToolEntry.linked(
        id="aws-mcp",
        kind=ToolKind.MCP,
        source="aws",
        title="AWS MCP Server",
        description="300+ API",
        recipe={"type": "mcp", "command": "aws-mcp"},
        region="us-east-1",
    )

    # Assert
    assert entry.ownership is Ownership.LINKED
    assert entry.recipe["command"] == "aws-mcp"
    assert entry.region == "us-east-1"


def test_owned_roundtrip() -> None:
    entry = ToolEntry.owned(
        id="x", kind=ToolKind.RULE, source="self",
        title="t", description="d", body="본문", tags=("a", "b"),
    )
    assert ToolEntry.from_markdown(entry.to_markdown()) == entry


def test_vendored_roundtrip_with_overlay() -> None:
    entry = ToolEntry.vendored(
        id="aws-iam", kind=ToolKind.SKILL, source="aws",
        title="AWS IAM", description="d",
        upstream="aws/.../aws-iam", synced_at="2026-06-29",
        tags=("vendor:aws",),
        overlay=Overlay(tags=("mine",), boundaries=("prod-gate",), notes="n"),
    )
    assert ToolEntry.from_markdown(entry.to_markdown()) == entry


def test_linked_roundtrip() -> None:
    entry = ToolEntry.linked(
        id="aws-mcp", kind=ToolKind.MCP, source="aws",
        title="AWS MCP", description="d",
        recipe={"command": "aws-mcp", "args": ["--profile", "dev"]},
        region="eu-central-1", tags=("vendor:aws",),
    )
    assert ToolEntry.from_markdown(entry.to_markdown()) == entry


def test_has_tag() -> None:
    entry = ToolEntry.owned(
        id="x", kind=ToolKind.SKILL, source="self",
        title="t", description="d", body="b", tags=("role:devops", "vendor:aws"),
    )
    assert entry.has_tag("vendor:aws")
    assert not entry.has_tag("role:dev")


# ── alias·surface (Phase 4.6 후속, 2026-07-03) ───────────────────────
#
# 실측: 같은 도구가 이름 둘을 가진다 — 카탈로그는 .mcp.json의 원래 이름(exa),
# 사용 추적은 런타임 네임스페이스(plugin_<플러그인>_exa). alias가 둘을 잇는다.
# surface는 "표면 통제권" 축: 플러그인이 표면을 관리하면 pouch는 관측만.


def test_linked_roundtrip_with_aliases_and_surface() -> None:
    from pouch.catalog.model import SURFACE_PLUGIN

    entry = ToolEntry.linked(
        id="exa", kind=ToolKind.MCP, source="ecc",
        title="exa", description="d", recipe={"command": "npx"},
        aliases=("plugin_everything-claude-code_exa",),
        surface=SURFACE_PLUGIN,
    )
    assert ToolEntry.from_markdown(entry.to_markdown()) == entry


def test_alias_map_maps_runtime_name_to_catalog_id() -> None:
    from pouch.catalog.model import alias_map

    exa = ToolEntry.linked(
        id="exa", kind=ToolKind.MCP, source="ecc", title="exa",
        description="d", recipe={}, aliases=("plugin_ecc_exa",),
    )
    plain = ToolEntry.linked(
        id="plain", kind=ToolKind.MCP, source="me", title="p",
        description="d", recipe={},
    )

    mapping = alias_map([exa, plain])

    assert mapping == {"plugin_ecc_exa": "exa"}
