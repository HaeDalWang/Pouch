"""로깅 tracker 계약 검증 — PostToolUse 페이로드 → 사용 이벤트.

핵심 위험지점: Skill 툴이 이름을 어느 필드에 싣는지. 문서엔 명시 없어
`tool_input.skill`로 가정하되, 틀려도 hook이 죽지 않도록 방어적으로 매핑한다.

  ① Skill 툴 → tool_input.skill 이 entry_id
  ② mcp__<server>__<tool> → <server> 가 entry_id (linked entry id)
  ③ 추적 안 하는 툴(Bash/Edit…) → None
  ④ 깨진/빈 페이로드 → None (hook이 절대 죽지 않는다)
  ⑤ record_usage: 매핑되면 ts를 붙여 로그에 append, 안 되면 무시
"""

from __future__ import annotations

from pathlib import Path

from pouch.evolution.tracker import entry_id_from_payload, record_usage
from pouch.evolution.usage_log import read_events


def test_contract1_skill_maps_to_skill_field() -> None:
    payload = {"tool_name": "Skill", "tool_input": {"skill": "python-review"}}
    assert entry_id_from_payload(payload) == "python-review"


def test_contract2_mcp_maps_to_server() -> None:
    payload = {"tool_name": "mcp__aws-mcp__call_aws", "tool_input": {}}
    assert entry_id_from_payload(payload) == "aws-mcp"


def test_contract2_mcp_with_underscored_server() -> None:
    # 실제 aws-core: mcp__plugin_aws-core_aws-mcp__aws___call_aws
    payload = {"tool_name": "mcp__plugin_aws-core_aws-mcp__aws___call_aws"}
    assert entry_id_from_payload(payload) == "plugin_aws-core_aws-mcp"


def test_contract3_untracked_tools_map_to_none() -> None:
    for name in ("Bash", "Edit", "Write", "Read", "Grep"):
        assert entry_id_from_payload({"tool_name": name}) is None


def test_contract4_broken_payload_maps_to_none() -> None:
    assert entry_id_from_payload({}) is None
    assert entry_id_from_payload({"tool_name": "Skill"}) is None  # tool_input 없음
    assert entry_id_from_payload({"tool_name": "Skill", "tool_input": {}}) is None
    assert entry_id_from_payload({"tool_name": ""}) is None
    assert entry_id_from_payload({"tool_name": "mcp__"}) is None  # server 비어있음


def test_contract5_record_appends_when_mapped(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    payload = {"tool_name": "Skill", "tool_input": {"skill": "aws-iam"}}

    record_usage(payload, now="2026-07-01T12:00:00", log_path=log)

    events = read_events(log_path=log)
    assert len(events) == 1
    assert events[0].entry_id == "aws-iam"
    assert events[0].ts == "2026-07-01T12:00:00"


def test_contract5_record_ignores_untracked(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"

    record_usage({"tool_name": "Bash", "tool_input": {"command": "ls"}}, now="t", log_path=log)

    assert read_events(log_path=log) == []
