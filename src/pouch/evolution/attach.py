"""attach 후보 — 진화의 반쪽 "붙는다". 순수 함수.

세 종류의 신호:
  reattach : 카탈로그에 있는데 표면에 없고 + 최근 썼다 → 다시 올리자고 제안
  adopt    : 카탈로그 밖인데 최근 자주 쓴다 → 편입(import) 안내만 (자동 없음)
  observe  : 표면을 플러그인이 관리하는 도구를 최근 썼다 → 관측만.
             재부착을 제안하면 이미 살아있는 서버를 .mcp.json에 중복 등록하는
             거짓말이 된다(표면 통제권이 pouch에 없음).

usage의 entry_id는 alias_map으로 카탈로그 정식 id에 접어 비교한다 — 런타임
별칭(plugin_<플러그인>_<서버>)과 카탈로그 id(<서버>)가 같은 도구이기 때문.

신호는 최근 창(_WINDOW_DAYS) 안의 사용만 인정한다. 창(7일) < stale 임계(30일)
이므로, stale로 방금 떨어진 도구의 옛 기록이 곧바로 재부착 신호로 되돌아오는
진동(oscillation)이 구조적으로 불가능하다 — drop과 attach가 같은 로그를 읽어도
서로 다른 시간대를 본다.
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.evolution.aggregate import aggregate_usage, canonicalize_stats, events_within
from pouch.evolution.usage_log import UsageEvent

_WINDOW_DAYS = 7  # stale 임계(30일)보다 반드시 짧아야 진동이 차단된다
_ADOPT_MIN_COUNT = 3  # 스쳐간 도구까지 편입 제안하면 노이즈
_KIND_REATTACH = "reattach"
_KIND_ADOPT = "adopt"
_KIND_OBSERVE = "observe"
_KIND_ORDER = {_KIND_REATTACH: 0, _KIND_ADOPT: 1, _KIND_OBSERVE: 2}


@dataclass(frozen=True)
class AttachCandidate:
    """주머니로 당겨올(또는 관측할) 후보."""

    entry_id: str
    kind: str  # "reattach" | "adopt" | "observe"
    count: int
    last_used: str


def attach_candidates(
    events: list[UsageEvent],
    *,
    catalog_ids: set[str],
    active_ids: set[str],
    now: str,
    alias_map: dict[str, str] | None = None,
    plugin_surfaced: set[str] = frozenset(),
    window_days: int = _WINDOW_DAYS,
    adopt_min_count: int = _ADOPT_MIN_COUNT,
) -> list[AttachCandidate]:
    """최근 창 안의 사용에서 당겨올 후보를 뽑는다(제안만, 아무것도 안 붙임).

    reattach는 1회 사용도 신호다(내가 아는 도구를 다시 찾았다는 뜻).
    adopt는 임계 이상 반복돼야 신호다(모르는 도구는 우연일 수 있다).
    observe는 정보일 뿐 행동이 없다(표면 통제권이 pouch에 없음).
    """
    recent = aggregate_usage(events_within(events, now=now, window_days=window_days))
    stats = canonicalize_stats(recent, alias_map or {})

    found: list[AttachCandidate] = []
    for entry_id, stat in stats.items():
        if entry_id in active_ids:
            continue
        if entry_id in plugin_surfaced:
            found.append(
                AttachCandidate(entry_id, _KIND_OBSERVE, stat.count, stat.last_used)
            )
        elif entry_id in catalog_ids:
            found.append(
                AttachCandidate(entry_id, _KIND_REATTACH, stat.count, stat.last_used)
            )
        elif stat.count >= adopt_min_count:
            found.append(
                AttachCandidate(entry_id, _KIND_ADOPT, stat.count, stat.last_used)
            )
    return sorted(found, key=lambda c: (_KIND_ORDER[c.kind], -c.count, c.entry_id))
