"""파일 호스트 자동 갱신·누수 방지 검증.

두 불변식을 못박는다:
- 누수 방지: 프로젝트 기억은 steering 파일에 절대 안 들어간다(전역만).
- 자동 갱신: 링크된 상태에서 기억이 바뀌면 스냅샷이 다시 써진다(낡음 해소).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.hosts.filesync import refresh_linked, render_file_body
from pouch.hosts.kiro import KiroSteeringAdapter
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType
from pouch.memory.store import MemoryStore

adapter = KiroSteeringAdapter()


def _entry(name: str, scope: MemoryScope, desc: str) -> MemoryEntry:
    return MemoryEntry(
        name=name, description=desc, body="본문", type=MemoryType.USER, scope=scope
    )


@pytest.fixture
def kiro_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "kiro"
    home.mkdir()
    monkeypatch.setenv("KIRO_HOME", str(home))
    return home


def test_render_excludes_project_memories() -> None:
    entries = [
        _entry("global-fact", MemoryScope.GLOBAL, "전역 사실"),
        _entry("proj-secret", MemoryScope.PROJECT, "프로젝트 비밀"),
    ]
    body = render_file_body(entries)
    assert "global-fact" in body
    assert "proj-secret" not in body  # 프로젝트 기억은 새면 안 된다


def test_refresh_only_touches_linked(kiro_home: Path) -> None:
    # 링크 안 된 상태 → 아무 파일도 새로 만들지 않는다.
    refreshed = refresh_linked([_entry("g", MemoryScope.GLOBAL, "x")])
    assert refreshed == []
    assert not adapter.is_linked()


def test_refresh_rewrites_linked_snapshot(kiro_home: Path) -> None:
    adapter.link("옛 본문")  # 이제 링크됨
    refreshed = refresh_linked([_entry("new-fact", MemoryScope.GLOBAL, "새 사실")])
    assert refreshed == ["kiro"]
    text = adapter.content_path().read_text(encoding="utf-8")
    assert "new-fact" in text  # 스냅샷이 새 기억으로 갱신됨


def test_store_save_auto_refreshes(
    kiro_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 전역 기억을 store로 저장하면 링크된 steering 파일이 자동 갱신된다.
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "pouch"))
    adapter.link("초기")  # 링크 상태로 만든다
    store = MemoryStore(global_dir=tmp_path / "gmem", project_dir=None)
    store.save(_entry("auto-mem", MemoryScope.GLOBAL, "자동 반영 대상"))
    assert "auto-mem" in adapter.content_path().read_text(encoding="utf-8")


def test_store_project_save_does_not_leak(
    kiro_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 프로젝트 기억 저장은 steering 파일을 건드리지 않는다(전역 스코프만 동기화).
    adapter.link("초기 본문")
    store = MemoryStore(global_dir=tmp_path / "gmem", project_dir=tmp_path / "pmem")
    store.save(_entry("proj-only", MemoryScope.PROJECT, "프로젝트 전용"))
    assert "proj-only" not in adapter.content_path().read_text(encoding="utf-8")
