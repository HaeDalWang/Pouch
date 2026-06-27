"""Claude Code settings.json 안전 조작.

조작 함수는 입력 dict를 변경하지 않고 새 dict를 반환한다(immutability).
파일 IO는 분리해 두어 순수 로직만 단위 테스트할 수 있다.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

# SessionStart에 등록할 명령. 이 문자열로 설치 여부를 식별한다.
POUCH_HOOK_COMMAND = "pouch memory context"


def load_settings(path: Path) -> dict:
    """설정 파일을 읽는다. 없거나 비어있으면 빈 dict."""
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}


def is_installed(settings: dict) -> bool:
    """pouch SessionStart hook이 이미 등록돼 있는지."""
    for group in settings.get("hooks", {}).get("SessionStart", []):
        for hook in group.get("hooks", []):
            if hook.get("command") == POUCH_HOOK_COMMAND:
                return True
    return False


def with_hook_installed(settings: dict) -> dict:
    """pouch hook이 추가된 새 설정을 반환한다(멱등). 기존 hook은 보존."""
    if is_installed(settings):
        return settings
    updated = copy.deepcopy(settings)
    hooks = updated.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])
    session_start.append({"hooks": [{"type": "command", "command": POUCH_HOOK_COMMAND}]})
    return updated


def with_hook_removed(settings: dict) -> dict:
    """pouch hook만 제거한 새 설정을 반환한다. 빈 컨테이너는 정리한다."""
    if not is_installed(settings):
        return settings
    updated = copy.deepcopy(settings)
    cleaned_groups = []
    for group in updated.get("hooks", {}).get("SessionStart", []):
        kept = [h for h in group.get("hooks", []) if h.get("command") != POUCH_HOOK_COMMAND]
        if kept:
            cleaned_groups.append({**group, "hooks": kept})
    if cleaned_groups:
        updated["hooks"]["SessionStart"] = cleaned_groups
    else:
        updated["hooks"].pop("SessionStart", None)
        if not updated["hooks"]:
            updated.pop("hooks", None)
    return updated


def write_settings(path: Path, settings: dict) -> Path | None:
    """설정을 기록한다. 기존 파일이 있었으면 백업하고 그 경로를 반환한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if path.exists():
        backup = path.with_name(path.name + ".bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return backup
