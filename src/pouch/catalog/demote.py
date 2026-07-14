"""demote — 카탈로그 → 소스 스테이징 강등. promote의 거울상.

정책([[pouch-import-gate-policy]]): promote가 "가리키기(소스)→진입(카탈로그)"라면
demote는 그 역이다 — 안 쓰는 도구를 카탈로그에서 소스로 되돌린다. 옛 import가
실사용과 무관하게 카탈로그에 직행시킨 도구들(194 마이그레이션)을 관문 뒤로
되돌리는 통로.

promote와 갈리는 지점은 하나: promote는 소스본을 남기지만(백과사전 페이지),
demote는 진짜 *이동*이라 카탈로그 원본을 지운다("그대로 옮기기": 파일 이동만).
카탈로그 엔트리가 overlay까지 실은 authoritative 복사본이라 통째로 옮긴다 —
개인화는 소스본에 보존되어 재진입(promote) 시 되살아난다.
"""

from __future__ import annotations

from pouch.catalog.model import ToolEntry
from pouch.catalog.store import CatalogStore


def demote(
    entry_id: str,
    *,
    source_store: CatalogStore,
    catalog_store: CatalogStore,
) -> ToolEntry | None:
    """카탈로그의 항목을 소스로 강등한다. 카탈로그에 없으면 None(옮길 게 없음).

    소스에 먼저 저장한 뒤 카탈로그에서 지운다 — 순서가 안전장치다: 저장이
    성공한 것만 지우므로, 중간에 죽어도 카탈로그본이 남아 유실이 없다(멱등 재실행).
    """
    entry = catalog_store.get(entry_id)
    if entry is None:
        return None

    source_store.save(entry)
    catalog_store.delete(entry_id)
    return entry
