"""카탈로그 저장소 — `~/.pouch/catalog/<id>.md` 플랫 파일 레지스트리."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pouch import paths
from pouch.catalog.model import Ownership, ToolEntry, ToolKind


class CatalogStore:
    """ToolEntry를 읽고 쓰고, 태그·ownership·kind로 검색한다."""

    def __init__(self, catalog_dir: Path | None = None) -> None:
        self._dir = catalog_dir or paths.catalog_dir()

    def save(self, entry: ToolEntry) -> Path:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{entry.id}.md"
        path.write_text(entry.to_markdown(), encoding="utf-8")
        return path

    def get(self, entry_id: str) -> ToolEntry | None:
        path = self._dir / f"{entry_id}.md"
        if not path.exists():
            return None
        return ToolEntry.from_markdown(path.read_text(encoding="utf-8"))

    def delete(self, entry_id: str) -> bool:
        """항목 파일을 지운다. 있었으면 True, 없었으면 False(멱등).

        drop은 카탈로그를 안 건드리지만("떨어진다≠삭제된다") migrate(강등)는 진짜
        이동이라 원본을 지워야 한다 — 지우는 쪽은 demote가 소스로 옮긴 뒤 호출한다.
        """
        path = self._dir / f"{entry_id}.md"
        if not path.exists():
            return False
        path.unlink()
        return True

    def list(self) -> Iterator[ToolEntry]:
        if not self._dir.exists():
            return
        for path in sorted(self._dir.glob("*.md")):
            yield ToolEntry.from_markdown(path.read_text(encoding="utf-8"))

    def search(
        self,
        *,
        tags: tuple[str, ...] | None = None,
        ownership: Ownership | None = None,
        kind: ToolKind | None = None,
    ) -> list[ToolEntry]:
        """조건을 모두(AND) 만족하는 항목을 반환한다. 태그도 모두 포함해야 한다."""
        results: list[ToolEntry] = []
        for entry in self.list():
            if tags and not all(entry.has_tag(tag) for tag in tags):
                continue
            if ownership is not None and entry.ownership is not ownership:
                continue
            if kind is not None and entry.kind is not kind:
                continue
            results.append(entry)
        return results
