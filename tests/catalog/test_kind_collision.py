"""같은 이름, 다른 종류 — 조용히 덮어쓰지 않는다.

장부는 평면(`<id>.md`)이라 종류가 달라도 이름이 같으면 한 자리를 다툰다. 실측
2026-07-21: `agent-sort`·`context-budget`·`rules-distill`이 스킬과 명령으로 둘 다
존재해, 훑기가 스킬을 명령으로 소리 없이 덮었다. 덮어쓰기는 데이터 손실이므로
거절하고 이유를 알린다(인질 금지보다 우선하는 원칙 — 조용한 손실 금지).
"""

from __future__ import annotations

import pytest

from pouch.catalog.importer import import_vendored_doc
from pouch.catalog.model import ToolKind
from pouch.catalog.store import CatalogStore

_NOW = "2026-07-21T10:00:00"


def _doc(tmp_path, rel: str, name: str) -> "object":
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: 설명\n---\n\n본문\n", encoding="utf-8")
    return path


def test_same_id_different_kind_is_refused(tmp_path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "cat")
    import_vendored_doc(
        _doc(tmp_path, "a/thing.md", "thing"), store, kind=ToolKind.SKILL,
        upstream="a", synced_at=_NOW,
    )

    with pytest.raises(ValueError, match="이미 skill로 담겨"):
        import_vendored_doc(
            _doc(tmp_path, "b/thing.md", "thing"), store, kind=ToolKind.COMMAND,
            upstream="b", synced_at=_NOW,
        )


def test_the_first_one_survives_intact(tmp_path) -> None:
    """거절당해도 먼저 담긴 것은 멀쩡해야 한다 — 손실이 없다는 게 요점이다."""
    store = CatalogStore(catalog_dir=tmp_path / "cat")
    import_vendored_doc(
        _doc(tmp_path, "a/thing.md", "thing"), store, kind=ToolKind.SKILL,
        upstream="a", synced_at=_NOW,
    )

    with pytest.raises(ValueError):
        import_vendored_doc(
            _doc(tmp_path, "b/thing.md", "thing"), store, kind=ToolKind.COMMAND,
            upstream="b", synced_at=_NOW,
        )

    assert store.get("thing").kind is ToolKind.SKILL


def test_reimporting_the_same_kind_still_works(tmp_path) -> None:
    """같은 종류 재import는 멱등하게 그대로 — 막는 건 종류가 바뀔 때뿐이다."""
    store = CatalogStore(catalog_dir=tmp_path / "cat")
    path = _doc(tmp_path, "a/thing.md", "thing")
    import_vendored_doc(path, store, kind=ToolKind.SKILL, upstream="a", synced_at=_NOW)

    entry = import_vendored_doc(
        path, store, kind=ToolKind.SKILL, upstream="a", synced_at=_NOW
    )

    assert entry.kind is ToolKind.SKILL
