"""reconcile 배선 — usage 로그를 읽어 소스→카탈로그 진입을 실제로 적용한다.

순수 선택(promote_candidates)과 원자 진입(promote)을 잇는 얇은 glue. attach의
canonicalize·alias_map을 그대로 재사용해 런타임 별칭(plugin_<플러그인>_<도구>)을
카탈로그 정식 id로 접은 뒤 판정한다 — 안 그러면 usage의 별칭이 소스 id와 안 맞아
진입이 안 걸린다.
"""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.evolution.orchestrate import reconcile
from pouch.evolution.usage_log import UsageEvent, append_event


def _source_skill(entry_id: str) -> ToolEntry:
    return ToolEntry.linked(
        id=entry_id, kind=ToolKind.SKILL, source="ecc",
        title=entry_id, description="d", recipe={}, surface="plugin",
    )


def _stores(tmp_path: Path) -> tuple[CatalogStore, CatalogStore]:
    source = CatalogStore(catalog_dir=tmp_path / "sources")
    catalog = CatalogStore(catalog_dir=tmp_path / "catalog")
    return source, catalog


def test_used_source_tool_enters_catalog(tmp_path: Path) -> None:
    # Arrange — exa가 소스에만 있고, 사용 기록에 한 번 찍혔다.
    source, catalog = _stores(tmp_path)
    source.save(_source_skill("exa"))
    usage = tmp_path / "usage.jsonl"
    append_event(UsageEvent("exa", "2026-07-13T09:00:00"), log_path=usage)

    # Act
    promoted = reconcile(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 카탈로그로 진입, 소스엔 그대로 남는다.
    assert promoted == ["exa"]
    assert catalog.get("exa") is not None
    assert source.get("exa") is not None


def test_unused_source_tools_stay_staged(tmp_path: Path) -> None:
    # Arrange — 셋 다 소스에 있지만 아무것도 안 썼다(빈 로그).
    source, catalog = _stores(tmp_path)
    for tool in ("exa", "context7", "aws-mcp"):
        source.save(_source_skill(tool))
    usage = tmp_path / "usage.jsonl"

    # Act
    promoted = reconcile(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 카탈로그 안 넘침(②의 핵심).
    assert promoted == []
    assert list(catalog.list()) == []


def test_runtime_alias_is_canonicalized_before_entry(tmp_path: Path) -> None:
    # Arrange — 소스 mcp는 alias(plugin_ecc_aws-mcp)를 갖고, 로그엔 alias로 찍힌다.
    source, catalog = _stores(tmp_path)
    source.save(
        ToolEntry.linked(
            id="aws-mcp", kind=ToolKind.MCP, source="ecc",
            title="aws", description="d", recipe={}, surface="plugin",
            aliases=("plugin_ecc_aws-mcp",),
        )
    )
    usage = tmp_path / "usage.jsonl"
    append_event(UsageEvent("plugin_ecc_aws-mcp", "2026-07-13T09:00:00"), log_path=usage)

    # Act
    promoted = reconcile(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 별칭을 정식 id로 접어 진입시킨다.
    assert promoted == ["aws-mcp"]
    assert catalog.get("aws-mcp") is not None


def test_already_entered_is_not_repromoted(tmp_path: Path) -> None:
    # Arrange — 이미 카탈로그에 있는 도구를 또 썼다.
    source, catalog = _stores(tmp_path)
    source.save(_source_skill("exa"))
    catalog.save(_source_skill("exa"))
    usage = tmp_path / "usage.jsonl"
    append_event(UsageEvent("exa", "2026-07-13T09:00:00"), log_path=usage)

    # Act
    promoted = reconcile(source_store=source, catalog_store=catalog, usage_path=usage)

    # Assert — 재진입 없음(멱등).
    assert promoted == []
