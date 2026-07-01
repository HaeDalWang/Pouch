"""활성 표면 상태 사이드카 — `~/.pouch/state.json`. 라이프사이클 기록.

정책: 상태 저장은 사이드카 분리. 카탈로그(레지스트리)와 분리해 churn 데이터가
overlay/body와 안 엉키게 한다. 버려도 되는 별도 레이어.

"떨어진다 ≠ 삭제된다"의 상태 표현: drop은 status=dropped일 뿐, installed_at
기록은 보존한다(비활성을 재추천 안 하는 판단의 근거). now는 주입한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch import paths

_STATUS_ACTIVE = "active"
_STATUS_DROPPED = "dropped"


def _state_path(state_path: Path | None) -> Path:
    return state_path or paths.state_path()


def load_state(*, state_path: Path | None = None) -> dict[str, dict]:
    """상태를 읽는다. 없거나 비어있으면 빈 dict."""
    path = _state_path(state_path)
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}


def _save_state(state: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def record_installed(entry_id: str, *, now: str, state_path: Path | None = None) -> None:
    """설치(또는 재부착)를 기록한다 — installed_at 갱신 + status=active.

    재부착이면 installed_at을 새로 찍어 never-used 시계를 리셋한다.
    """
    path = _state_path(state_path)
    state = load_state(state_path=path)
    state[entry_id] = {"installed_at": now, "status": _STATUS_ACTIVE}
    _save_state(state, path)


def mark_dropped(entry_id: str, *, state_path: Path | None = None) -> None:
    """drop을 기록한다 — status=dropped. installed_at 기록은 보존한다."""
    path = _state_path(state_path)
    state = load_state(state_path=path)
    if entry_id not in state:
        return
    state[entry_id] = {**state[entry_id], "status": _STATUS_DROPPED}
    _save_state(state, path)


def active_entries(*, state_path: Path | None = None) -> dict[str, str]:
    """status=active인 항목만 {entry_id: installed_at}로 돌려준다."""
    return {
        entry_id: rec["installed_at"]
        for entry_id, rec in load_state(state_path=state_path).items()
        if rec.get("status") == _STATUS_ACTIVE
    }
