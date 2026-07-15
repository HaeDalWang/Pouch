"""registry 검증 — 훅/파일 두 종류 조회와 설치 탐지.

훅 호스트 탐지는 설정 디렉토리 유무(첫 연결도 잡히게 파일이 아닌 부모로). 파일
호스트 탐지는 전역 설치 신호(~/.kiro 존재). 세 경로를 임시로 격리해 실제 홈을
건드리지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.hosts.registry import (
    all_names,
    detect_file_supported,
    detect_hook_installed,
    get_file_adapter,
    get_hook_adapter,
)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # 세 호스트를 모두 없는 경로로 밀어둔다(기본 상태 = 아무것도 감지 안 됨).
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    monkeypatch.setenv("KIRO_HOME", str(tmp_path / "no-kiro"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_get_hook_adapter_by_name() -> None:
    assert get_hook_adapter("claude") is not None
    assert get_hook_adapter("codex") is not None
    assert get_hook_adapter("kiro") is None  # kiro는 파일 호스트
    assert get_hook_adapter("nope") is None


def test_get_file_adapter_by_name() -> None:
    assert get_file_adapter("kiro") is not None
    assert get_file_adapter("claude") is None  # claude는 훅 호스트


def test_all_names_covers_both_kinds() -> None:
    names = all_names()
    assert names == ["claude", "codex", "kiro"]


def test_detect_none_when_nothing_present(isolated: Path) -> None:
    assert detect_hook_installed() == []
    assert detect_file_supported() == []


def test_detect_claude_when_dir_exists(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    claude = isolated / "claude"
    claude.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    detected = [a.name for a in detect_hook_installed()]
    assert detected == ["claude"]


def test_detect_kiro_when_home_exists(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kiro = isolated / "kiro"
    kiro.mkdir()
    monkeypatch.setenv("KIRO_HOME", str(kiro))
    detected = [a.name for a in detect_file_supported()]
    assert detected == ["kiro"]
