"""제안 장부 사이드카 — `~/.pouch/proposals.json`. 먼저 내미는 제안의 기억.

정책([[pouch-proactive-nudge-policy]]): 잔소리 방어(간격·묵히기)는 작은 상태를
요구한다 — "이 제안 언제 심었나 / 몇 번째인가". usage.jsonl·state.json과 같은
정신: 카탈로그(레지스트리)와 분리된 사이드카, 버려도 되는 층(지우면 다시 침묵부터
시작), now는 주입한다(결정적 테스트 + hook이 이벤트 시각을 소유).

정밀화가 이긴다: 묵히기는 *반자동*이다 — 무시하는 게 곧 "지금 아님"이라
명시 스누즈("언제까지 묵혀달라")를 저장하지 않는다. 장부는 심은 사실만 기록하고,
"물러남"(조각 4)이 이 위에서 last_shown_at·shown_count로 유효 침묵을 계산한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch import paths


def _ledger_path(ledger_path: Path | None) -> Path:
    return ledger_path or paths.proposals_ledger_path()


def load_ledger(*, ledger_path: Path | None = None) -> dict[str, dict]:
    """장부를 읽는다. 없거나 비어있으면 빈 dict."""
    path = _ledger_path(ledger_path)
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}


def _save_ledger(ledger: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def record_shown(
    proposal_id: str, *, now: str, ledger_path: Path | None = None
) -> None:
    """제안을 한 번 심었음을 기록한다 — last_shown_at 갱신 + shown_count 증가."""
    path = _ledger_path(ledger_path)
    ledger = load_ledger(ledger_path=path)
    prior = ledger.get(proposal_id, {})
    ledger[proposal_id] = {
        "last_shown_at": now,
        "shown_count": prior.get("shown_count", 0) + 1,
    }
    _save_ledger(ledger, path)


def last_shown(proposal_id: str, *, ledger_path: Path | None = None) -> str | None:
    """마지막으로 심은 시각. 심은 적 없으면 None."""
    rec = load_ledger(ledger_path=ledger_path).get(proposal_id)
    return rec.get("last_shown_at") if rec else None


def shown_count(proposal_id: str, *, ledger_path: Path | None = None) -> int:
    """지금까지 심은 횟수. 심은 적 없으면 0."""
    rec = load_ledger(ledger_path=ledger_path).get(proposal_id)
    return rec.get("shown_count", 0) if rec else 0
