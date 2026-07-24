"""promote — 소스 스테이징 → 카탈로그 진입. 관문 (다)의 유일한 진입 연산.

정책([[pouch-import-gate-policy]]): import는 번들을 소스(`~/.pouch/sources/`)에만
담고 카탈로그엔 아무것도 안 올린다(진입 0). 사용자가 실제로 쓰거나(reconcile),
install/세트로 명시하면 그 도구가 여기서 카탈로그로 진입한다. 진입은 항상 이 한
연산을 거친다 — "가리키기(소스)"와 "진입(카탈로그)"을 위치로 가른 두 store 사이의 다리.

소스에서는 지우지 않는다: 백과사전 페이지는 남고 노트에 옮긴 것만 카탈로그다. drop돼도
소스로 되짚어 재진입할 수 있다. kind·ownership·surface·alias는 소스본 그대로 옮긴다
(스코핑 A에서 맞춘 관측 스텁 성격을 진입 시점에 다시 판단하지 않는다).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from pouch.catalog.model import ToolEntry
from pouch.catalog.store import CatalogStore


def promote(
    entry_id: str,
    *,
    source_store: CatalogStore,
    catalog_store: CatalogStore,
) -> ToolEntry | None:
    """소스의 항목을 카탈로그로 진입시킨다. 소스에 없으면 None(옮길 게 없음).

    이미 카탈로그에 있으면 그쪽 overlay(진입 후 쌓인 개인화)를 보존한다 — 소스본은
    overlay가 없어 그대로 덮으면 개인화가 뭉개진다(재import 멱등과 같은 정신).
    """
    staged = source_store.get(entry_id)
    if staged is None:
        return None

    existing = catalog_store.get(entry_id)
    if existing is not None and existing.overlay is not None:
        staged = replace(staged, overlay=existing.overlay)

    catalog_store.save(staged)
    return staged


def promote_from_repo(
    scoped_id: str,
    *,
    index_root: "Path",
    catalog_store: CatalogStore,
) -> ToolEntry | None:
    """`<저장소>/<도구>`를 저장소 색인에서 카탈로그로 진입시킨다 (Phase 4.8 ④).

    카탈로그 안 정체는 맨 이름이다 — 장부는 평면이라 "/"를 못 담고, 출처는
    upstream(클론 안 경로)이 이미 말한다. 같은 이름이 **딴 출처**에서 이미 와
    있으면 조용히 덮지 않고 거부한다(ValueError). **같은 출처**의 재진입은 기존
    항목을 그대로 돌려준다 — 개인화 overlay가 뭉개지지 않는 재설치 경로.

    "/"가 없거나 색인에 없으면 None — 이 문의 소관이 아니다(호출부가 다른 문을
    이미 거쳐 왔다).
    """
    repo_name, sep, tool_id = scoped_id.partition("/")
    if not sep or not repo_name or not tool_id:
        return None

    staged = CatalogStore(catalog_dir=index_root / repo_name).get(tool_id)
    if staged is None:
        return None

    existing = catalog_store.get(tool_id)
    if existing is not None:
        if (existing.upstream, existing.recipe) == (staged.upstream, staged.recipe):
            return existing  # 같은 출처 — 재진입은 기존(개인화 포함) 유지
        raise ValueError(
            f"'{tool_id}'는 이미 카탈로그에 있습니다(다른 출처). "
            f"'{scoped_id}'를 들이려면 먼저 기존 것을 정리하세요."
        )

    catalog_store.save(staged)
    return staged
