"""vendored-import — upstream을 추적하는 도구를 카탈로그에 들인다.

핵심 원칙(vendored): 본체(body)는 절대 복사/저장하지 않는다. upstream 경로만
참조로 들고, 개인화(태그·boundary·메모)는 본체와 분리된 overlay에 쌓는다.
재import는 upstream 갱신만 반영하고 overlay는 보존한다(멱등).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import frontmatter

from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore


@dataclass(frozen=True)
class SkillSource:
    """SKILL.md에서 읽은 메타데이터(본문 제외)."""

    id: str
    title: str
    description: str
    upstream: str


def read_skill(path: Path, *, upstream: str) -> SkillSource:
    """SKILL.md의 frontmatter만 읽는다. 본문은 의도적으로 버린다(vendored).

    본문을 메모리에 들이지 않기 위해 metadata만 취하고 content는 참조하지 않는다.
    """
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata
    name = str(meta["name"])
    return SkillSource(
        id=name,
        title=str(meta.get("title") or name),
        description=str(meta.get("description", "")),
        upstream=upstream,
    )


def import_vendored_skill(
    path: Path,
    store: CatalogStore,
    *,
    upstream: str,
    synced_at: str,
    source: str = "aws",
    tags: tuple[str, ...] = ("vendor:aws",),
) -> ToolEntry:
    """SKILL.md를 vendored 항목으로 들인다. 재import 시 기존 overlay를 보존한다."""
    src = read_skill(path, upstream=upstream)

    existing = store.get(src.id)
    preserved_overlay = existing.overlay if existing else None
    preserved_tags = existing.tags if existing else tags

    entry = ToolEntry.vendored(
        id=src.id,
        kind=ToolKind.SKILL,
        source=source,
        title=src.title,
        description=src.description,
        upstream=src.upstream,
        synced_at=synced_at,
        overlay=preserved_overlay,
        tags=preserved_tags,
    )
    store.save(entry)
    return entry


def apply_overlay(store: CatalogStore, entry_id: str, overlay: Overlay) -> ToolEntry:
    """vendored 항목에 개인화 overlay를 붙인다. 본체(upstream)는 건드리지 않는다."""
    entry = store.get(entry_id)
    if entry is None:
        raise ValueError(f"카탈로그에 '{entry_id}' 항목이 없습니다.")
    updated = replace(entry, overlay=overlay)
    store.save(updated)
    return updated
