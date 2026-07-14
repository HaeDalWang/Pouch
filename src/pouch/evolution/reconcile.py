"""reconcile — 실사용을 소스→카탈로그 진입 결정으로. 순수 함수.

관문 (다)([[pouch-import-gate-policy]])의 진입 트리거 "실사용 1회". import가 소스에만
재워둔 도구를 사용자가 실제로 쓰면, 그 도구를 카탈로그로 진입시킬 후보로 고른다.

문턱 1회: 사용 통계에 나타났다는 것 자체가 "최소 한 번 씀"이라 별도 카운트가 필요
없다. adopt의 3회 방어(드물게 스친 미지 도구는 우연)는 여기 불필요 — 사용자가 그
번들을 일부러 import한 사실이 이미 우연을 걷어냈기 때문(정책 근거).

window를 안 본다: promote는 단조다(한번 진입하면 유지, drop은 소스를 안 건드림).
drop↔attach 진동 방지용 최근 창(attach.py)이 여기선 불필요하다. "쓴 적 있으면
카탈로그에 속한다" — 옛 사용도 인정하려면 full_stats(접힌 요약 포함)를 넘긴다.

IO(로그 읽기·store 쓰기)는 orchestrate가 한다. 여기선 stats·id 집합만 받는 순수 선택.
"""

from __future__ import annotations

from pouch.evolution.aggregate import UsageStat


def promote_candidates(
    stats: dict[str, UsageStat],
    *,
    source_ids: set[str],
    catalog_ids: set[str],
) -> list[str]:
    """카탈로그로 진입시킬 후보 id를 고른다(정렬된 결정적 순서).

    조건: 소스에 있고(source_ids) + 카탈로그엔 아직 없고(not in catalog_ids) +
    사용 기록에 나타남(stats). stats의 id는 이미 canonicalize를 거쳤다고 가정한다
    (런타임 별칭이 카탈로그 정식 id로 접힌 상태 — orchestrate가 alias_map으로 처리).
    """
    return sorted(
        entry_id
        for entry_id in stats
        if entry_id in source_ids and entry_id not in catalog_ids
    )
