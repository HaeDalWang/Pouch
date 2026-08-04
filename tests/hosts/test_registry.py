"""registry 검증 — 훅/파일 두 종류 조회와 설치 탐지.

훅 호스트 탐지는 설정 디렉토리 유무(첫 연결도 잡히게 파일이 아닌 부모로). 파일
호스트 탐지는 전역 설치 신호. 경로를 임시로 격리해 실제 홈을 건드리지 않는다.

파일 호스트 목록은 지금 비어 있다 — 유일했던 Kiro를 2026-08-04에 지원 중단했다
(BACKLOG P6). 조회·탐지 함수는 그대로 살아 있고 "없음"을 정직하게 답한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.hosts.registry import (
    all_names,
    detect_file_supported,
    detect_hook_installed,
    file_adapters,
    get_file_adapter,
    get_hook_adapter,
)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # 두 호스트를 모두 없는 경로로 밀어둔다(기본 상태 = 아무것도 감지 안 됨).
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_get_hook_adapter_by_name() -> None:
    assert get_hook_adapter("claude") is not None
    assert get_hook_adapter("codex") is not None
    assert get_hook_adapter("nope") is None


def test_no_file_hosts_registered() -> None:
    """파일 호스트는 지금 없다 — 조회는 죽지 않고 None/빈 목록을 준다."""
    assert file_adapters() == ()
    assert get_file_adapter("kiro") is None  # 지원 중단(BACKLOG P6)
    assert get_file_adapter("claude") is None  # claude는 훅 호스트


def test_all_names_covers_registered_hosts() -> None:
    assert all_names() == ["claude", "codex"]


def test_detect_none_when_nothing_present(isolated: Path) -> None:
    assert detect_hook_installed() == []
    assert detect_file_supported() == []


def test_detect_claude_when_dir_exists(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    claude = isolated / "claude"
    claude.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    detected = [a.name for a in detect_hook_installed()]
    assert detected == ["claude"]
