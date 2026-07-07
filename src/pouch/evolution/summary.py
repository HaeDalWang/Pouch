"""접힌 사용 요약 — 오래된 이벤트의 누적을 보존하는 사이드카.

usage.jsonl은 최근 상세만 들고, 경계(180일) 밖 이벤트는 여기에 entry_id별
누적으로 접힌다. 개별 시각은 흐려지되 누적 횟수(습관 신호)는 남는다.

`compacted_through`는 "이 시각까지 접었다"는 마커다. 집계가 jsonl에서 이 시각
이전(이미 접힌 구간)을 무시하게 해, jsonl 재작성이 실패해도 이중 계산이 없다
(멱등). usage는 버려도 되는 레이어라 깨진 요약은 빈 것으로 폴백한다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from pouch import paths
from pouch.evolution.aggregate import UsageStat


@dataclass(frozen=True)
class UsageSummary:
    """접힌 과거 누적. entries=entry_id별 통계, compacted_through=접힘 경계 시각."""

    entries: dict[str, UsageStat] = field(default_factory=dict)
    compacted_through: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "entries": {
                    entry_id: {"count": stat.count, "last_used": stat.last_used}
                    for entry_id, stat in self.entries.items()
                },
                "compacted_through": self.compacted_through,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_dict(cls, data: dict) -> UsageSummary:
        entries = {
            entry_id: UsageStat(count=raw["count"], last_used=raw["last_used"])
            for entry_id, raw in data.get("entries", {}).items()
        }
        return cls(entries=entries, compacted_through=data.get("compacted_through"))


def load_summary(*, path: Path | None = None) -> UsageSummary:
    """요약을 읽는다. 없거나 깨졌으면 빈 요약(무한성장보다 안전한 폴백)."""
    target = path or paths.usage_summary_path()
    if not target.exists():
        return UsageSummary()
    try:
        return UsageSummary.from_dict(json.loads(target.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, TypeError):
        # 버려도 되는 레이어 — 깨진 요약은 빈 것으로 시작한다(최근 상세는 jsonl에 살아있다).
        return UsageSummary()


def save_summary(summary: UsageSummary, *, path: Path | None = None) -> None:
    """요약을 원자적으로 쓴다(tmp 작성 후 교체 — 반쯤 덮이지 않게)."""
    target = path or paths.usage_summary_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(summary.to_json(), encoding="utf-8")
    os.replace(tmp, target)  # 원자적 교체
