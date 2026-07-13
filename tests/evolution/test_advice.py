"""조언 분류 계약 검증 — plugin 관측 사용을 진화 조언으로 (A→B 전환 조각 1).

정책([[pouch-evolution-management-layer]]): 진화 = 행위(drop/reattach)가 아니라
조언. surface:plugin(관측 전용)은 손댈 수 없는 대상이 아니라 조언 신호다.
pouch는 ECC 표면을 강제로 안 바꾼다 — 소유자에게 사람 말로 조언만.

핵심 절제(추측 잔소리 회피): plugin 도구를 "안 씀"으로 판정하는 건 관측 증거가
있을 때만. 한 번도 본 적 없는 plugin 도구는 침묵한다 — "본 적 없으니 꺼"는
추측이라 우리가 계속 피한 잔소리 함정. 관측한 것만 조언한다.

  ① plugin + 최근 씀 → reinforce(강화, 잘 쓰는 것으로 관측)
  ② plugin + 예전엔 썼는데 지금 stale → suggest_off("ECC에서 꺼볼까요")
  ③ plugin + 한 번도 안 봄(stats에 없음) → 조언 없음(침묵, 추측 안 함)
  ④ non-plugin(pouch 소유) → 여기서 안 다룸(drop/reattach 경로 소유)
  ⑤ 순수 함수 — now·stale_days 주입, 시계·IO 없음
"""

from __future__ import annotations

from pouch.catalog.model import Overlay, ToolEntry, ToolKind, SURFACE_PLUGIN
from pouch.evolution.advice import Advice, plan_advice
from pouch.evolution.aggregate import UsageStat


def _plugin(id: str) -> ToolEntry:
    return ToolEntry.linked(
        id=id, kind=ToolKind.MCP, source="ecc", title=id, description=f"{id} 설명",
        recipe={}, surface=SURFACE_PLUGIN,
    )


def _owned(id: str) -> ToolEntry:
    return ToolEntry.owned(
        id=id, kind=ToolKind.SKILL, source="s", title=id, description="d", body="b",
    )


_NOW = "2026-07-13T00:00:00"


def test_contract1_plugin_recently_used_is_reinforce() -> None:
    entries = [_plugin("exa")]
    stats = {"exa": UsageStat(count=15, last_used="2026-07-12T00:00:00")}  # 어제

    advices = plan_advice(entries, stats, now=_NOW, stale_days=30)

    assert len(advices) == 1
    assert isinstance(advices[0], Advice)
    assert advices[0].target == "exa"
    assert advices[0].kind == "reinforce"
    assert advices[0].count == 15


def test_contract2_plugin_gone_stale_is_suggest_off() -> None:
    entries = [_plugin("context7")]
    # 60일 전 마지막 사용 → stale(30일 임계 넘음)
    stats = {"context7": UsageStat(count=9, last_used="2026-05-14T00:00:00")}

    advices = plan_advice(entries, stats, now=_NOW, stale_days=30)

    assert advices[0].kind == "suggest_off"
    assert advices[0].target == "context7"


def test_contract3_plugin_never_seen_is_silent() -> None:
    # 카탈로그엔 있지만 usage에 한 번도 안 나타남 → 추측 안 함(침묵)
    entries = [_plugin("unused-plugin-tool")]
    stats: dict[str, UsageStat] = {}

    assert plan_advice(entries, stats, now=_NOW, stale_days=30) == []


def test_contract4_non_plugin_not_handled_here() -> None:
    # pouch 소유(surface 없음)는 drop/reattach 경로가 소유 — 여기선 조언 안 냄
    entries = [_owned("my-skill")]
    stats = {"my-skill": UsageStat(count=5, last_used="2026-07-12T00:00:00")}

    assert plan_advice(entries, stats, now=_NOW, stale_days=30) == []


def test_contract5_is_pure() -> None:
    entries = [_plugin("exa")]
    stats = {"exa": UsageStat(count=3, last_used="2026-07-12T00:00:00")}

    assert plan_advice(entries, stats, now=_NOW, stale_days=30) == plan_advice(
        entries, stats, now=_NOW, stale_days=30
    )


def test_reinforce_before_suggest_off_then_id() -> None:
    # 정렬: 강화(잘 쓰는 것 먼저) → 끄기 제안, 각각 id 순(결정적)
    entries = [_plugin("z-used"), _plugin("a-stale"), _plugin("a-used")]
    stats = {
        "z-used": UsageStat(count=5, last_used="2026-07-12T00:00:00"),
        "a-used": UsageStat(count=2, last_used="2026-07-12T00:00:00"),
        "a-stale": UsageStat(count=1, last_used="2026-05-01T00:00:00"),
    }

    advices = plan_advice(entries, stats, now=_NOW, stale_days=30)

    assert [(a.kind, a.target) for a in advices] == [
        ("reinforce", "a-used"),
        ("reinforce", "z-used"),
        ("suggest_off", "a-stale"),
    ]
