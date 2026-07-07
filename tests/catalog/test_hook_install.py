"""훅 설치/내리기 계약 — 조리법을 settings.json에 배선하고 걷어낸다.

훅 설치란 파일 복사가 아니라 Claude 설정(settings.json)에 "이 사건이 나면
이 명령을 실행하라"를 써넣는 일이다. pouch가 자기 훅 둘(기억 주입·사용 기록)을
걸 때 쓰는 안전장치(새 dict 반환·백업 동반)를 그대로 탄다.

  ① install_entry(kind=hook) → settings.json 해당 사건 아래 배선이 생긴다
  ② 두 번 설치해도 배선은 하나 (다시 실행해도 결과가 같다)
  ③ 기존 배선(pouch 자체 훅 포함)은 건드리지 않는다 + 백업(.bak)을 남긴다
  ④ uninstall_entry(kind=hook) → 그 훅의 배선만 걷어내고 남은 것은 보존
  ⑤ 설치는 state.json에 active로 기록된다 (진화가 볼 데이터)
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch.catalog.install import install_entry
from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.uninstall import uninstall_entry
from pouch.evolution.state import active_entries
from pouch.hooks.settings import load_settings


def _hook_entry(entry_id: str = "pre-bash-check", command: str = "node check.js") -> ToolEntry:
    return ToolEntry.linked(
        id=entry_id,
        kind=ToolKind.HOOK,
        source="ecc",
        title=entry_id,
        description="Bash 실행 전 점검",
        recipe={
            "event": "PreToolUse",
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": command}],
        },
    )


def _commands_under(settings: dict, event: str) -> list[str]:
    return [
        h.get("command")
        for group in settings.get("hooks", {}).get(event, [])
        for h in group.get("hooks", [])
    ]


def test_contract1_install_wires_event_in_settings(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"

    install_entry(
        _hook_entry(), skills_dir=tmp_path / "skills",
        mcp_config_path=tmp_path / ".mcp.json", settings_path=settings_path,
        state_path=tmp_path / "state.json",
    )

    settings = load_settings(settings_path)
    assert "node check.js" in _commands_under(settings, "PreToolUse")
    # matcher도 함께 배선된다
    group = settings["hooks"]["PreToolUse"][0]
    assert group["matcher"] == "Bash"


def test_contract2_reinstall_does_not_duplicate(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    kwargs = dict(
        skills_dir=tmp_path / "skills", mcp_config_path=tmp_path / ".mcp.json",
        settings_path=settings_path, state_path=tmp_path / "state.json",
    )

    install_entry(_hook_entry(), **kwargs)
    install_entry(_hook_entry(), **kwargs)

    settings = load_settings(settings_path)
    assert _commands_under(settings, "PreToolUse").count("node check.js") == 1


def test_contract3_preserves_existing_hooks_and_backs_up(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    existing = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "pouch memory context"}]}
            ]
        }
    }
    settings_path.write_text(json.dumps(existing), encoding="utf-8")

    install_entry(
        _hook_entry(), skills_dir=tmp_path / "skills",
        mcp_config_path=tmp_path / ".mcp.json", settings_path=settings_path,
        state_path=tmp_path / "state.json",
    )

    settings = load_settings(settings_path)
    # pouch 자체 훅은 그대로
    assert "pouch memory context" in _commands_under(settings, "SessionStart")
    # 백업이 남았다
    assert settings_path.with_name("settings.json.bak").exists()


def test_contract4_uninstall_removes_only_this_hook(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    kwargs = dict(
        skills_dir=tmp_path / "skills", mcp_config_path=tmp_path / ".mcp.json",
        settings_path=settings_path, state_path=tmp_path / "state.json",
    )
    install_entry(_hook_entry("hook-a", "node a.js"), **kwargs)
    install_entry(_hook_entry("hook-b", "node b.js"), **kwargs)

    uninstall_entry(
        _hook_entry("hook-a", "node a.js"),
        skills_dir=tmp_path / "skills", mcp_config_path=tmp_path / ".mcp.json",
        settings_path=settings_path,
    )

    commands = _commands_under(load_settings(settings_path), "PreToolUse")
    assert "node a.js" not in commands
    assert "node b.js" in commands  # 남은 훅은 보존


def test_contract5_install_records_active_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    install_entry(
        _hook_entry(), skills_dir=tmp_path / "skills",
        mcp_config_path=tmp_path / ".mcp.json",
        settings_path=tmp_path / "settings.json", state_path=state_path,
    )

    assert "pre-bash-check" in active_entries(state_path=state_path)
