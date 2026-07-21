"""테스트 전역 격리 — 실제 홈(`~/.pouch`, `~/.claude`)을 절대 건드리지 않는다.

autouse로 POUCH_HOME·CLAUDE_CONFIG_DIR을 테스트별 tmp로 돌린다. 개별 테스트가
monkeypatch로 다시 지정하면 그 값이 이긴다(autouse가 먼저, 테스트가 나중).
install_entry가 state.json을 기록하게 되면서 이 격리가 필수가 됐다.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path_factory, monkeypatch) -> None:
    pouch_home = tmp_path_factory.mktemp("pouch_home")
    claude_home = tmp_path_factory.mktemp("claude_home")
    backup_home = tmp_path_factory.mktemp("pouch_backups")
    monkeypatch.setenv("POUCH_HOME", str(pouch_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    # 백업 목적지도 격리 — migrate·backup 커맨드가 실제 ~/pouch-backups에 쓰지 않게.
    monkeypatch.setenv("POUCH_BACKUP_DIR", str(backup_home))
    # 나머지 하네스 홈도 격리 — 훑기(sweep)가 실제 ~/.codex·~/.kiro의 도구통을
    # 읽어들이면 테스트가 이 머신에 깔린 것에 따라 달라진다(2026-07-21).
    monkeypatch.setenv("CODEX_HOME", str(tmp_path_factory.mktemp("codex_home")))
    monkeypatch.setenv("KIRO_HOME", str(tmp_path_factory.mktemp("kiro_home")))
