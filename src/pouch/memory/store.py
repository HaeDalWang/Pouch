"""메모리 저장소 — 글로벌/프로젝트 두 스코프에 걸친 플랫 파일 CRUD.

쓰기(save/forget) 후에는 해당 스코프의 MEMORY.md 인덱스를 자동 갱신해
인덱스가 본문과 어긋나지 않도록 구조적으로 보장한다("규칙은 코드로").
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from pouch import paths
from pouch.memory.index import INDEX_FILENAME, write_index
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState


class MemoryStore:
    """`<dir>/<name>.md` 형태로 메모리를 읽고 쓴다.

    디렉토리를 주입받으므로 테스트에서 임시 경로를 쉽게 끼울 수 있다.
    기본값은 `paths` 모듈이 결정한 실제 위치다(프로젝트 디렉토리는 없을 수 있음).
    """

    def __init__(
        self,
        global_dir: Path | None = None,
        project_dir: Path | None = None,
    ) -> None:
        self._global_dir = global_dir or paths.global_memory_dir()
        self._project_dir = (
            project_dir if project_dir is not None else paths.project_memory_dir()
        )

    def _dir_for(self, scope: MemoryScope) -> Path | None:
        return self._global_dir if scope is MemoryScope.GLOBAL else self._project_dir

    def _path_for(self, name: str, scope: MemoryScope) -> Path | None:
        directory = self._dir_for(scope)
        return (directory / f"{name}.md") if directory else None

    def save(self, entry: MemoryEntry) -> Path:
        """메모리를 해당 스코프에 저장한다. 같은 이름은 덮어쓴다(멱등)."""
        path = self._path_for(entry.name, entry.scope)
        if path is None:
            raise ValueError(
                f"'{entry.scope.value}' 스코프 디렉토리를 결정할 수 없습니다. "
                "프로젝트 루트(.git/.pouch)가 있는지 확인하세요."
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry.to_markdown(), encoding="utf-8")
        self._reindex(entry.scope)
        return path

    def get(self, name: str, scope: MemoryScope) -> MemoryEntry | None:
        """이름과 스코프로 메모리를 읽는다. 없으면 None."""
        path = self._path_for(name, scope)
        if path is None or not path.exists():
            return None
        return MemoryEntry.from_markdown(name, path.read_text(encoding="utf-8"))

    def promote(self, entry: MemoryEntry) -> MemoryEntry:
        """pending을 확인하고 인덱스(INDEXED)로 올린다. save가 재인덱싱까지 보장."""
        updated = replace(entry, state=MemoryState.INDEXED)
        self.save(updated)
        return updated

    def demote(self, entry: MemoryEntry) -> MemoryEntry:
        """인덱스에서 강등(ARCHIVED)한다 — 파일은 남고 recall로만 소환된다.

        "떨어진다 ≠ 삭제된다"의 기억판: forget과 달리 파일을 지우지 않는다.
        """
        updated = replace(entry, state=MemoryState.ARCHIVED)
        self.save(updated)
        return updated

    def forget(self, name: str, scope: MemoryScope) -> bool:
        """메모리를 삭제한다. 실제로 지웠으면 True, 없었으면 False."""
        path = self._path_for(name, scope)
        if path is None or not path.exists():
            return False
        path.unlink()
        self._reindex(scope)
        return True

    def list(self) -> Iterator[MemoryEntry]:
        """글로벌 + 프로젝트의 모든 메모리를 순회한다."""
        yield from self._iter_scope(MemoryScope.GLOBAL)
        yield from self._iter_scope(MemoryScope.PROJECT)

    def _iter_scope(self, scope: MemoryScope) -> Iterator[MemoryEntry]:
        directory = self._dir_for(scope)
        if not directory or not directory.exists():
            return
        for path in sorted(directory.glob("*.md")):
            if path.name == INDEX_FILENAME:
                continue
            yield MemoryEntry.from_markdown(path.stem, path.read_text(encoding="utf-8"))

    def _reindex(self, scope: MemoryScope) -> None:
        directory = self._dir_for(scope)
        if not directory or not directory.exists():
            return
        write_index(directory, list(self._iter_scope(scope)))
