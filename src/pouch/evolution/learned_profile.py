"""학습된 관심사 — 실사용에서 손에 맞은(core) 도구의 토큰을 관심사로 승격한다.

개인화 학습 레인 1의 다음 걸음(Phase 4.5). 핵심 도구 인식(core_tools)이 "무엇을
손에 쥐었나"를 배웠다면, 여기선 그 도구들이 달고 온 토큰(설명·태그·id)을 모아
"내가 실제로 무엇에 관심 있나"를 배운다. 추천의 관심사가 init 답변(stated)만이
아니라 실사용(learned)에서도 자란다 — "쓸수록 진짜 프로필로 학습".

**실측 재프레이밍.** 로드맵은 "태그 승격"이라 불렀지만 실측 태그는 죽어있다
(0/201, [pool.py](pool.py) 참고). 그래서 승격 신호를 태그에서 pool 토큰(설명 중심,
살아있는 신호)으로 옮긴다 — pool/similar이 이미 한 태그→설명토큰 피벗과 같은 정신.
지어내지 않고 있는 신호만 접는다.

**파생이지 저장이 아니다.** usage.jsonl 위에서 매번 다시 난다(프로필 기억을 mutate
안 함 → retrofit 빚 없음). 콜드 스타트(core 없음)면 빈 결과 → stated로 자연 폴백.

**승격 단위는 core.** 단순 빈도가 아니라 지속·빈도로 손에 맞은 도구(core_entry_ids)만
— burst≠핵심, 최근성 면역을 그대로 상속한다("손에 맞음"의 단일 정의 재사용).

순수 함수 — 시계도 IO도 없다.
"""

from __future__ import annotations

from collections import Counter

from pouch.catalog.model import ToolEntry
from pouch.evolution.core_tools import CoreConfig, core_entry_ids
from pouch.evolution.pool import build_pool
from pouch.evolution.usage_log import UsageEvent


def learned_interests(
    events: list[UsageEvent],
    entries: list[ToolEntry],
    *,
    alias_map: dict[str, str] | None = None,
    config: CoreConfig = CoreConfig(),
) -> list[tuple[str, int]]:
    """core 도구가 달고 온 토큰을 (토큰, 공유한 core 도구 수) 내림차순으로 준다(순수).

    여러 core 도구가 공유하는 토큰일수록 강한 관심 신호다(수렴). 카운트는 도구당
    한 번씩만 센다(같은 도구가 토큰을 여러 번 써도 1) — 신호는 "몇 개의 손에 맞은
    도구가 이 토큰을 달고 오나"이지 설명 안 반복 빈도가 아니다.

    core_entry_ids가 별칭을 정식 id로 접으므로 build_pool의 카탈로그 id와 바로 맞는다.
    카탈로그 밖 core 도구(pool에 없음)는 승격할 토큰이 없어 자연히 빠진다 —
    status·report가 core를 catalog_ids로 거르는 것과 같은 결과.
    """
    core = core_entry_ids(events, alias_map=alias_map, config=config)
    if not core:
        return []
    counter: Counter[str] = Counter()
    for pool_entry in build_pool(entries):
        if pool_entry.id in core:
            counter.update(pool_entry.tokens)  # frozenset → 도구당 토큰 1회
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def learned_interest_tokens(
    events: list[UsageEvent],
    entries: list[ToolEntry],
    *,
    alias_map: dict[str, str] | None = None,
    config: CoreConfig = CoreConfig(),
) -> set[str]:
    """학습된 관심사를 매칭용 토큰 집합으로(순수). 추천 관심사 축에 유니온한다."""
    return {token for token, _ in learned_interests(events, entries, alias_map=alias_map, config=config)}
