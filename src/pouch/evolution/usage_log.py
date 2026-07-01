"""사이드카 사용 로그 — `~/.pouch/usage.jsonl` append-only 이벤트.

카탈로그(레지스트리)와 분리된 라이프사이클 레이어. churn 데이터가
overlay/body와 엉키지 않도록 별도 파일에 쌓는다. 버려도 되는 레이어다.

ts는 주입한다 — 로그는 시계를 만들지 않는다(결정적 테스트 + hook이 이벤트 시각 소유).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pouch import paths


@dataclass(frozen=True)
class UsageEvent:
    """한 번의 도구 사용. entry_id는 카탈로그 <id>, ts는 ISO8601 문자열."""

    entry_id: str
    ts: str

    def to_json(self) -> str:
        return json.dumps({"entry_id": self.entry_id, "ts": self.ts}, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> UsageEvent:
        return cls(entry_id=data["entry_id"], ts=data["ts"])


def append_event(event: UsageEvent, *, log_path: Path | None = None) -> None:
    """이벤트 한 줄을 로그 끝에 덧붙인다. 부모 디렉토리는 필요 시 만든다."""
    path = log_path or paths.usage_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(event.to_json() + "\n")


def read_events(*, log_path: Path | None = None) -> list[UsageEvent]:
    """적재 순서대로 이벤트를 읽는다. 없으면 빈 리스트, 깨진 줄은 건너뛴다."""
    path = log_path or paths.usage_log_path()
    if not path.exists():
        return []
    events: list[UsageEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(UsageEvent.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            # append 도중 죽어 반쯤 쓰인 줄이 있어도 나머지는 유효하게 읽는다.
            continue
    return events
