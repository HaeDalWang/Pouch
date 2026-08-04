"""파일 호스트 자동 갱신·누수 방지 검증.

두 불변식을 못박는다:
- 누수 방지: 프로젝트 기억은 스냅샷 파일에 절대 안 들어간다(전역만).
- 자동 갱신: 링크된 상태에서 기억이 바뀌면 스냅샷이 다시 써진다(낡음 해소).

**진짜 어댑터 대신 가짜를 쓴다.** 유일했던 파일 호스트(Kiro)를 2026-08-04에
지원 중단해 레지스트리가 비었기 때문(BACKLOG P6). 검증 대상은 어느 하네스가
아니라 filesync의 두 불변식이므로, 계약만 채운 가짜로 충분하다 — 파일로 연결하는
하네스가 다시 생겼을 때 이 그물이 그대로 받는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.hosts.filesync import refresh_linked, render_file_body
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType
from pouch.memory.store import MemoryStore


class FakeFileHost:
    """FileHostAdapter 계약을 채운 최소 구현 — 파일 하나에 body를 쓴다."""

    name = "fake"
    display_name = "Fake File Host"

    def __init__(self, path: Path) -> None:
        self._path = path

    def is_supported(self) -> bool:
        return True

    def content_path(self) -> Path:
        return self._path

    def is_linked(self) -> bool:
        return self._path.exists()

    def link(self, body: str) -> Path | None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(body, encoding="utf-8")
        return None

    def unlink(self) -> bool:
        if not self._path.exists():
            return False
        self._path.unlink()
        return True

    def post_install_notes(self) -> list[str]:
        return []


def _entry(name: str, scope: MemoryScope, desc: str) -> MemoryEntry:
    return MemoryEntry(
        name=name, description=desc, body="본문", type=MemoryType.USER, scope=scope
    )


@pytest.fixture
def adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeFileHost:
    """가짜 파일 호스트를 레지스트리에 끼워 넣는다(이 테스트 동안만)."""
    fake = FakeFileHost(tmp_path / "snapshot" / "memory.md")
    monkeypatch.setattr("pouch.hosts.registry._FILE_ADAPTERS", (fake,))
    return fake


def test_render_excludes_project_memories() -> None:
    entries = [
        _entry("global-fact", MemoryScope.GLOBAL, "전역 사실"),
        _entry("proj-secret", MemoryScope.PROJECT, "프로젝트 비밀"),
    ]
    body = render_file_body(entries)
    assert "global-fact" in body
    assert "proj-secret" not in body  # 프로젝트 기억은 새면 안 된다


def test_refresh_only_touches_linked(adapter: FakeFileHost) -> None:
    # 링크 안 된 상태 → 아무 파일도 새로 만들지 않는다.
    refreshed = refresh_linked([_entry("g", MemoryScope.GLOBAL, "x")])
    assert refreshed == []
    assert not adapter.is_linked()


def test_refresh_rewrites_linked_snapshot(adapter: FakeFileHost) -> None:
    adapter.link("옛 본문")  # 이제 링크됨
    refreshed = refresh_linked([_entry("new-fact", MemoryScope.GLOBAL, "새 사실")])
    assert refreshed == ["fake"]
    text = adapter.content_path().read_text(encoding="utf-8")
    assert "new-fact" in text  # 스냅샷이 새 기억으로 갱신됨


def test_store_save_auto_refreshes(
    adapter: FakeFileHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 전역 기억을 store로 저장하면 링크된 스냅샷이 자동 갱신된다.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "pouch"))
    adapter.link("초기")  # 링크 상태로 만든다
    store = MemoryStore(global_dir=tmp_path / "gmem", project_dir=None)
    store.save(_entry("auto-mem", MemoryScope.GLOBAL, "자동 반영 대상"))
    assert "auto-mem" in adapter.content_path().read_text(encoding="utf-8")


def test_store_project_save_does_not_leak(
    adapter: FakeFileHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 프로젝트 기억 저장은 스냅샷 파일을 건드리지 않는다(전역 스코프만 동기화).
    adapter.link("초기 본문")
    store = MemoryStore(global_dir=tmp_path / "gmem", project_dir=tmp_path / "pmem")
    store.save(_entry("proj-only", MemoryScope.PROJECT, "프로젝트 전용"))
    assert "proj-only" not in adapter.content_path().read_text(encoding="utf-8")
