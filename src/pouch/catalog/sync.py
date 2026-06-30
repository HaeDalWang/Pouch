"""sync — vendored 엔트리의 upstream을 재방문해 카탈로그를 최신으로 맞춘다.

import이 '처음 들이기'라면 sync는 '재방문'이다. body는 애초에 안 들고 있으니
(vendored) frontmatter만 다시 읽어 metadata와 synced_at을 갱신한다.
개인화(overlay)는 import_vendored_skill이 보존하므로 그대로 살아남는다.

owned(upstream 없음)·linked(외부 실행)는 sync 대상이 아니다 — 손대지 않는다.
"""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.importer import import_vendored_skill
from pouch.catalog.model import Ownership, ToolEntry
from pouch.catalog.store import CatalogStore


def sync_entry(store: CatalogStore, entry_id: str, *, synced_at: str) -> ToolEntry:
    """vendored 항목 하나를 upstream에서 재방문해 갱신한다.

    upstream 파일이 사라졌으면 FileNotFoundError를 그대로 올린다(조용히 삼키지 않음).
    vendored가 아니면 ValueError.
    """
    entry = store.get(entry_id)
    if entry is None:
        raise ValueError(f"카탈로그에 '{entry_id}' 항목이 없습니다.")
    if entry.ownership is not Ownership.VENDORED:
        raise ValueError(
            f"'{entry_id}'는 {entry.ownership.value}입니다. sync는 vendored만 대상으로 합니다."
        )
    if not entry.upstream:
        raise ValueError(f"'{entry_id}'에 upstream이 없어 sync할 수 없습니다.")

    upstream_path = Path(entry.upstream)
    if not upstream_path.exists():
        raise FileNotFoundError(
            f"'{entry_id}'의 upstream이 사라졌습니다: {entry.upstream}"
        )

    # import_vendored_skill이 기존 overlay·tags를 보존하며 metadata를 다시 읽는다.
    return import_vendored_skill(
        upstream_path,
        store,
        upstream=entry.upstream,
        synced_at=synced_at,
        source=entry.source,
    )


def sync_all(store: CatalogStore, *, synced_at: str) -> list[ToolEntry]:
    """카탈로그의 모든 vendored 항목을 sync한다. owned·linked는 건너뛴다."""
    synced: list[ToolEntry] = []
    for entry in store.search(ownership=Ownership.VENDORED):
        synced.append(sync_entry(store, entry.id, synced_at=synced_at))
    return synced
