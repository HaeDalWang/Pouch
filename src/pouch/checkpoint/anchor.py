"""정렬 앵커 사이드카 — 프로젝트별 `.pouch/anchor.json`. "이번 작업 목표"의 고정점.

정책(pouch-scope-boundary의 거울상): pouch는 세션 시작에 사용자를 주입한다. 이
앵커는 작업 시작에 "이번 목표"를 한 줄로 박아, ◆목표 슬롯이 매 요약마다 그대로
재사용할 재해석 없는 고정점을 만든다. ledger.py·state.json과 같은 정신 —
카탈로그와 분리된, 버려도 되는 라이프사이클 레이어(지우면 앵커 없음부터 시작),
now는 주입한다(결정적 테스트 + 호출자가 이벤트 시각을 소유).

세션 개념이 pouch에 없으므로 앵커의 임자는 *폴더*다 — 프로젝트 안에서 박은 목표는
그 프로젝트의 `.pouch/anchor.json`에, 프로젝트 밖 목표는 글로벌에 산다(자리 결정은
paths.resolve_anchor_path, 폴백 없음). 앵커가 하나뿐이라 A 프로젝트 목표가 B
프로젝트 세션 시작에 그대로 주입되던 사고(2026-07-21)를 자리로 막는다.

한 프로젝트 안에서는 여전히 단일 앵커다. set은 덮어쓴다 — 매 작업 시작에
에이전트가 첫 지시에서 목표를 뽑아 재설정하는 흐름을 전제한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pouch import paths


@dataclass(frozen=True)
class Anchor:
    """고정된 이번 작업 목표. goal은 ◆목표 슬롯에 그대로 재사용된다."""

    goal: str
    set_at: str


def _anchor_path(anchor_path: Path | None) -> Path:
    return anchor_path or paths.resolve_anchor_path()


def set_anchor(goal: str, *, now: str, anchor_path: Path | None = None) -> Anchor:
    """이번 작업 목표를 고정한다(기존 앵커는 덮어쓴다)."""
    path = _anchor_path(anchor_path)
    anchor = Anchor(goal=goal, set_at=now)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"goal": anchor.goal, "set_at": anchor.set_at}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return anchor


def load_anchor(*, anchor_path: Path | None = None) -> Anchor | None:
    """고정된 앵커를 읽는다. 없거나 비어있으면 None(첫 실행·clear 후 안전)."""
    path = _anchor_path(anchor_path)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    data = json.loads(raw)
    goal = data.get("goal")
    if not goal:
        return None
    return Anchor(goal=goal, set_at=data.get("set_at", ""))


def clear_anchor(*, anchor_path: Path | None = None) -> bool:
    """앵커를 비운다. 실제로 지웠으면 True, 애초에 없었으면 False."""
    path = _anchor_path(anchor_path)
    if not path.exists():
        return False
    path.unlink()
    return True
