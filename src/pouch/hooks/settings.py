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

# PostToolUse에 등록할 사용 로깅 명령 + 매처(Skill·MCP 호출만 추적).
POUCH_USAGE_HOOK_COMMAND = "pouch evolve log"
POUCH_USAGE_HOOK_MATCHER = "Skill|mcp__.*"


def load_settings(path: Path) -> dict:
    """설정 파일을 읽는다. 없거나 비어있으면 빈 dict."""
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}


def _has_command(settings: dict, event: str, command: str) -> bool:
    """특정 이벤트 그룹에 해당 명령이 등록돼 있는지."""
    for group in settings.get("hooks", {}).get(event, []):
        for hook in group.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


def _with_group_added(settings: dict, event: str, group: dict, command: str) -> dict:
    """이벤트에 hook 그룹을 추가한 새 설정을 반환한다(멱등). 기존 hook 보존."""
    if _has_command(settings, event, command):
        return settings
    updated = copy.deepcopy(settings)
    hooks = updated.setdefault("hooks", {})
    hooks.setdefault(event, []).append(group)
    return updated


def _with_command_removed(settings: dict, event: str, command: str) -> dict:
    """이벤트에서 해당 명령만 제거한 새 설정을 반환한다. 빈 컨테이너는 정리한다."""
    if not _has_command(settings, event, command):
        return settings
    updated = copy.deepcopy(settings)
    cleaned_groups = []
    for group in updated.get("hooks", {}).get(event, []):
        kept = [h for h in group.get("hooks", []) if h.get("command") != command]
        if kept:
            cleaned_groups.append({**group, "hooks": kept})
    if cleaned_groups:
        updated["hooks"][event] = cleaned_groups
    else:
        updated["hooks"].pop(event, None)
        if not updated["hooks"]:
            updated.pop("hooks", None)
    return updated


def is_installed(settings: dict) -> bool:
    """pouch SessionStart hook이 이미 등록돼 있는지."""
    return _has_command(settings, "SessionStart", POUCH_HOOK_COMMAND)


def with_hook_installed(settings: dict) -> dict:
    """pouch hook이 추가된 새 설정을 반환한다(멱등). 기존 hook은 보존."""
    group = {"hooks": [{"type": "command", "command": POUCH_HOOK_COMMAND}]}
    return _with_group_added(settings, "SessionStart", group, POUCH_HOOK_COMMAND)


def with_hook_removed(settings: dict) -> dict:
    """pouch hook만 제거한 새 설정을 반환한다. 빈 컨테이너는 정리한다."""
    return _with_command_removed(settings, "SessionStart", POUCH_HOOK_COMMAND)


def is_usage_hook_installed(settings: dict) -> bool:
    """pouch PostToolUse 사용 로깅 hook이 이미 등록돼 있는지."""
    return _has_command(settings, "PostToolUse", POUCH_USAGE_HOOK_COMMAND)


def with_usage_hook_installed(settings: dict) -> dict:
    """사용 로깅 hook(PostToolUse)이 추가된 새 설정을 반환한다(멱등)."""
    group = {
        "matcher": POUCH_USAGE_HOOK_MATCHER,
        "hooks": [{"type": "command", "command": POUCH_USAGE_HOOK_COMMAND}],
    }
    return _with_group_added(settings, "PostToolUse", group, POUCH_USAGE_HOOK_COMMAND)


def with_usage_hook_removed(settings: dict) -> dict:
    """사용 로깅 hook만 제거한 새 설정을 반환한다. 빈 컨테이너는 정리한다."""
    return _with_command_removed(settings, "PostToolUse", POUCH_USAGE_HOOK_COMMAND)


def _recipe_commands(recipe: dict) -> list[str]:
    """조리법 안의 명령 문자열들을 꺼낸다(배선·제거의 식별자)."""
    return [h.get("command", "") for h in recipe.get("hooks", []) if h.get("command")]


def with_recipe_installed(settings: dict, recipe: dict) -> dict:
    """카탈로그 훅 조리법을 배선한 새 설정을 반환한다(다시 해도 결과 같음).

    조리법 = {event, matcher?, hooks:[{type, command, ...}]}. pouch 자체 훅과
    같은 안전장치를 탄다: 입력 dict 불변, 기존 배선 보존, 명령 문자열로 식별.
    """
    event = recipe["event"]
    group: dict = {"hooks": recipe.get("hooks", [])}
    if recipe.get("matcher"):
        group["matcher"] = recipe["matcher"]
    updated = settings
    for command in _recipe_commands(recipe):
        updated = _with_group_added(updated, event, group, command)
    return updated


def with_recipe_removed(settings: dict, recipe: dict) -> dict:
    """카탈로그 훅 조리법의 배선만 걷어낸 새 설정을 반환한다. 나머지 보존."""
    event = recipe["event"]
    updated = settings
    for command in _recipe_commands(recipe):
        updated = _with_command_removed(updated, event, command)
    return updated


# 네이티브 메모리 스위치 — Claude Code 기본 메모리를 끄는 settings 키.
# false면 네이티브가 읽기·쓰기를 모두 멈춰(자동로드 주입 없음), pouch가 자리를 대체한다.
# ⚠️ 배선 시 이 키 이름을 공식 docs로 재확인한다 — 틀리면 조용한 무동작(안 꺼짐).
NATIVE_MEMORY_KEY = "autoMemoryEnabled"


def is_native_memory_disabled(settings: dict) -> bool:
    """Claude 네이티브 메모리가 꺼져 있는지(pouch가 대체 중인지)."""
    return settings.get(NATIVE_MEMORY_KEY) is False


def with_native_memory_disabled(settings: dict) -> dict:
    """네이티브 메모리를 끈 새 설정을 반환한다(멱등·기존 보존). A안 §1."""
    if is_native_memory_disabled(settings):
        return settings
    updated = copy.deepcopy(settings)
    updated[NATIVE_MEMORY_KEY] = False
    return updated


def with_native_memory_enabled(settings: dict) -> dict:
    """네이티브 메모리 스위치를 걷어낸 새 설정(되돌리기 — 키 제거로 기본값 복원)."""
    if NATIVE_MEMORY_KEY not in settings:
        return settings
    updated = copy.deepcopy(settings)
    updated.pop(NATIVE_MEMORY_KEY, None)
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
