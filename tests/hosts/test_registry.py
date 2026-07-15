"""registry 검증 — 이름 조회와 설치 탐지(디렉토리 기준).

탐지는 설정 파일이 아니라 그 부모 디렉토리 유무로 판단한다(첫 연결도 잡아야
하므로). 세 호스트 경로를 임시로 격리해 실제 홈을 건드리지 않고 검증한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.hosts.registry import (
    adapter_names,
    detect_installed,
    get_adapter,
)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # 세 호스트를 모두 없는 경로로 밀어둔다(기본 상태 = 아무것도 감지 안 됨).
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    monkeypatch.chdir(tmp_path)  # .git 없음 → Kiro 워크스페이스 미탐지
    return tmp_path


def test_get_adapter_by_name() -> None:
    assert get_adapter("claude") is not None
    assert get_adapter("codex") is not None
    assert get_adapter("kiro") is not None
    assert get_adapter("nope") is None


def test_adapter_names_order() -> None:
    assert adapter_names() == ["claude", "codex", "kiro"]


def test_detect_none_when_no_dirs(isolated: Path) -> None:
    assert detect_installed() == []


def test_detect_claude_when_dir_exists(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    claude = isolated / "claude"
    claude.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    detected = [a.name for a in detect_installed()]
    assert detected == ["claude"]


def test_detect_kiro_in_workspace(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = isolated / "proj"
    (project / ".git").mkdir(parents=True)
    (project / ".kiro" / "hooks").mkdir(parents=True)
    monkeypatch.chdir(project)
    detected = [a.name for a in detect_installed()]
    assert "kiro" in detected
