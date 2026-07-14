"""migrate 배선 — usage 로그를 읽어 카탈로그→소스 강등을 실제로 적용한다.

reconcile(진입)의 거울상. 순수 선택(demote_candidates)과 원자 강등(demote)을 잇는
얇은 glue. 옛 import가 실사용과 무관하게 카탈로그에 직행시킨 잉여(194)를 관문 뒤
소스로 되돌린다.

두 방어가 결정적이다:
  1. canonicalize — 런타임 별칭(plugin_<플러그인>_<도구>)을 정식 id로 접어야
     "exa를 썼다"가 카탈로그 exa에 닿아 잘못된 강등을 막는다(reconcile과 같은 방어).
  2. has_usage_signal — 훅·규칙·에이전트는 신호가 안 찍혀 항상 "안 씀"으로 보이므로
     강등에서 제외한다(drop과 같은 방어: 신호 없음 ≠ 안 쓰임).
"""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.evolution.orchestrate import migrate
from pouch.evolution.usage_log import UsageEvent, append_event


def _catalog_skill(entry_id: str, *, kind: ToolKind = ToolKind.SKILL) -> ToolEntry:
    return ToolEntry.linked(
        id=entry_id, kind=kind, source="ecc",
        title=entry_id, description="d", recipe={}, surface="plugin",
    )


def _stores(tmp_path: Path) -> tuple[CatalogStore, CatalogStore]:
    source = CatalogStore(catalog_dir=tmp_path / "sources")
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    return source, catalog


def test_unused_catalog_tool_is_demoted(tmp_path: Path) -> None:
    # Arrange — 카탈로그에만 있고(옛 import 직행) 아무것도 안 썼다.
    source, catalog = _stores(tmp_path)
    catalog.save(_catalog_skill("unused"))
    usage = tmp_path / "usage.jsonl"

    # Act
    demoted = migrate(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 소스로 강등, 카탈로그에선 사라진다.
    assert demoted == ["unused"]
    assert source.get("unused") is not None
    assert catalog.get("unused") is None


def test_used_catalog_tool_stays(tmp_path: Path) -> None:
    # Arrange — exa를 실제로 썼다.
    source, catalog = _stores(tmp_path)
    catalog.save(_catalog_skill("exa"))
    usage = tmp_path / "usage.jsonl"
    append_event(UsageEvent("exa", "2026-07-13T09:00:00"), log_path=usage)

    # Act
    demoted = migrate(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 강등 없음, 카탈로그 잔류(진입 유지).
    assert demoted == []
    assert catalog.get("exa") is not None


def test_runtime_alias_is_canonicalized_before_demote(tmp_path: Path) -> None:
    # Arrange — 카탈로그 mcp는 alias를 갖고, 로그엔 alias로 찍힌다.
    source, catalog = _stores(tmp_path)
    catalog.save(
        ToolEntry.linked(
            id="aws-mcp", kind=ToolKind.MCP, source="ecc",
            title="aws", description="d", recipe={}, surface="plugin",
            aliases=("plugin_ecc_aws-mcp",),
        )
    )
    usage = tmp_path / "usage.jsonl"
    append_event(UsageEvent("plugin_ecc_aws-mcp", "2026-07-13T09:00:00"), log_path=usage)

    # Act
    demoted = migrate(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 별칭을 정식 id로 접어 "썼다"로 인정 → 강등 안 함(잘못된 강등 방어).
    assert demoted == []
    assert catalog.get("aws-mcp") is not None


def test_non_signal_kinds_are_not_demoted(tmp_path: Path) -> None:
    # Arrange — 훅·규칙·에이전트는 신호가 안 찍힌다(빈 로그). 하지만 강등하면 안 됨.
    source, catalog = _stores(tmp_path)
    catalog.save(_catalog_skill("some-hook", kind=ToolKind.HOOK))
    catalog.save(_catalog_skill("some-rule", kind=ToolKind.RULE))
    catalog.save(_catalog_skill("some-agent", kind=ToolKind.AGENT))
    usage = tmp_path / "usage.jsonl"

    # Act
    demoted = migrate(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 신호 없음 ≠ 안 쓰임. 하나도 강등 안 됨(drop과 같은 방어).
    assert demoted == []
    assert catalog.get("some-hook") is not None
    assert catalog.get("some-rule") is not None
    assert catalog.get("some-agent") is not None


def test_mixed_demotes_only_unused_signal_kinds(tmp_path: Path) -> None:
    # Arrange — 안 쓴 스킬(강등 대상) + 쓴 스킬(잔류) + 안 쓴 훅(신호없음 제외).
    source, catalog = _stores(tmp_path)
    catalog.save(_catalog_skill("unused-skill"))
    catalog.save(_catalog_skill("used-skill"))
    catalog.save(_catalog_skill("some-hook", kind=ToolKind.HOOK))
    usage = tmp_path / "usage.jsonl"
    append_event(UsageEvent("used-skill", "2026-07-13T09:00:00"), log_path=usage)

    # Act
    demoted = migrate(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 안 쓴 스킬만 강등. 쓴 스킬·훅은 잔류.
    assert demoted == ["unused-skill"]
    assert catalog.get("unused-skill") is None
    assert catalog.get("used-skill") is not None
    assert catalog.get("some-hook") is not None


def test_migrate_reverses_reconcile(tmp_path: Path) -> None:
    # Arrange — reconcile로 진입시킨 뒤 사용 기록을 지우면(빈 로그) migrate가 되돌린다.
    from pouch.evolution.orchestrate import reconcile

    source, catalog = _stores(tmp_path)
    source.save(_catalog_skill("exa"))
    usage = tmp_path / "usage.jsonl"
    append_event(UsageEvent("exa", "2026-07-13T09:00:00"), log_path=usage)
    reconcile(source_store=source, catalog_store=catalog, usage_path=usage)
    assert catalog.get("exa") is not None

    # Act — 사용 기록 없는 빈 로그로 migrate.
    empty_usage = tmp_path / "empty.jsonl"
    demoted = migrate(source_store=source, catalog_store=catalog, usage_path=empty_usage)

    # Assert — 카탈로그에서 내려가고 소스엔 남는다(왕복 대칭).
    assert demoted == ["exa"]
    assert catalog.get("exa") is None
    assert source.get("exa") is not None
