"""사용 추적 — PostToolUse 페이로드를 사용 이벤트로 매핑해 적재한다.

신호 정책: 최근성 주축 + 횟수 보조. 여기선 "무엇이 한 번의 사용인가"만 정한다.
boundary 통과는 신호에서 제외(위험≠유용, 가드레일로 직교).

핵심 위험지점 — Skill 툴이 이름을 어느 필드에 싣는지는 문서에 명시가 없다.
`tool_input.skill`로 가정하되, 틀려도 hook이 죽지 않게 전 구간 방어적으로 매핑한다.
매핑 실패는 예외가 아니라 None이다: 추적은 best-effort, 절대 작업을 막지 않는다.
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.usage_log import UsageEvent, append_event

_MCP_PREFIX = "mcp__"
_MCP_SERVER_SEP = "__"


def entry_id_from_payload(payload: dict) -> str | None:
    """PostToolUse 페이로드에서 카탈로그 entry_id를 뽑는다. 못 뽑으면 None.

    - Skill  → tool_input.skill (설치 시 <id>와 일치)
    - mcp__<server>__<tool> → <server> (linked entry id)
    - 그 외(Bash/Edit/…) → None (추적 대상 아님)
    """
    tool_name = payload.get("tool_name") or ""

    if tool_name == "Skill":
        skill = (payload.get("tool_input") or {}).get("skill")
        return skill or None

    if tool_name.startswith(_MCP_PREFIX):
        rest = tool_name[len(_MCP_PREFIX) :]
        server = rest.split(_MCP_SERVER_SEP, 1)[0]
        return server or None

    return None


def record_usage(
    payload: dict, *, now: str, log_path: Path | None = None
) -> str | None:
    """페이로드가 추적 대상이면 ts를 붙여 로그에 append한다.

    now(현재 시각 ISO8601)는 주입한다 — hook 경계가 시각을 소유하고,
    순수 매핑은 시계를 만들지 않는다. 매핑된 entry_id를 반환(없으면 None).
    """
    entry_id = entry_id_from_payload(payload)
    if entry_id is None:
        return None
    append_event(UsageEvent(entry_id=entry_id, ts=now), log_path=log_path)
    return entry_id
