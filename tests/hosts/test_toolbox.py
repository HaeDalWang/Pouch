"""도구통 위치 — 어댑터가 "이 하네스는 도구를 어디 두나"를 안다.

훑기(sweep)가 하네스마다 경로를 하드코딩하지 않게 하는 칸이다. 새 하네스는
어댑터에 이 칸만 채우면 훑기에 자동으로 편입된다.
"""

from __future__ import annotations

from pathlib import Path

from pouch.hosts.base import LAYOUT_FILE, LAYOUT_PLUGIN_CACHE, LAYOUT_SKILLS_ROOT
from pouch.hosts.claude import ClaudeAdapter
from pouch.hosts.codex import CodexAdapter
from pouch.hosts.kiro import KiroSteeringAdapter
from pouch.hosts.registry import toolbox_hosts


def test_claude_toolbox_covers_skills_and_plugin_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))

    boxes = ClaudeAdapter().toolbox_paths()

    layouts = {box.layout: box.path for box in boxes}
    assert layouts[LAYOUT_SKILLS_ROOT] == tmp_path / "skills"
    assert layouts[LAYOUT_PLUGIN_CACHE] == tmp_path / "plugins" / "cache"


def test_codex_toolbox_follows_codex_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))

    paths_by_layout = {box.layout: box.path for box in CodexAdapter().toolbox_paths()}

    assert paths_by_layout[LAYOUT_SKILLS_ROOT] == tmp_path / "skills"
    assert paths_by_layout[LAYOUT_FILE] == tmp_path / "hooks.json"


def test_kiro_has_a_skills_toolbox(tmp_path, monkeypatch) -> None:
    """Kiro는 기억을 파일로만 받지만 도구통(skills/)은 따로 있다 — 실측 2026-07-21."""
    monkeypatch.setenv("KIRO_HOME", str(tmp_path))

    boxes = KiroSteeringAdapter().toolbox_paths()

    assert [box.path for box in boxes] == [tmp_path / "skills"]
    assert boxes[0].layout == LAYOUT_SKILLS_ROOT


def test_toolbox_hosts_covers_both_hook_and_file_hosts() -> None:
    """도구통은 훅형/파일형과 직교한다 — 양쪽 다 걷어온다."""
    names = {host.name for host in toolbox_hosts()}

    assert {"claude", "codex", "kiro"} <= names


def test_toolbox_paths_are_absolute() -> None:
    for host in toolbox_hosts():
        for box in host.toolbox_paths():
            assert isinstance(box.path, Path)
            assert box.path.is_absolute()
