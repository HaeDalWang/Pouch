"""reconcile — 실사용이 소스 스테이징을 카탈로그로 진입시킨다(순수 선택).

관문 (다)의 진입 트리거 중 "실사용 1회". promote_candidates는 사용 통계에서
"소스엔 있는데 카탈로그엔 아직 없는" id만 고른다 — 진입 대상. 문턱 1회는
"stats에 나타남 = 최소 1회 씀"이라 별도 카운트가 필요 없다(적으면 우연이라는
adopt의 3회 방어는 여기 불필요 — 사용자가 그 번들을 일부러 들인 사실이 우연 방어).
"""

from __future__ import annotations

from pouch.evolution.aggregate import UsageStat
from pouch.evolution.reconcile import promote_candidates


def _stat(count: int = 1, last_used: str = "2026-07-13T00:00:00") -> UsageStat:
    return UsageStat(count=count, last_used=last_used)


def test_used_source_tool_is_promote_candidate() -> None:
    # 소스에 있고 카탈로그엔 없는 도구를 1회 썼다 → 진입 대상.
    stats = {"exa": _stat(count=1)}
    result = promote_candidates(
        stats, source_ids={"exa"}, catalog_ids=set()
    )
    assert result == ["exa"]


def test_already_in_catalog_is_not_candidate() -> None:
    # 이미 진입한 건 다시 진입시킬 필요 없다.
    stats = {"exa": _stat()}
    result = promote_candidates(
        stats, source_ids={"exa"}, catalog_ids={"exa"}
    )
    assert result == []


def test_used_but_not_in_source_is_not_candidate() -> None:
    # 소스에도 없는 도구(진짜 미지)는 여기 대상 아님 — adopt 경로가 본다.
    stats = {"mystery": _stat(count=5)}
    result = promote_candidates(
        stats, source_ids={"exa"}, catalog_ids=set()
    )
    assert result == []


def test_unused_source_tool_stays_staged() -> None:
    # 소스에 있어도 안 쓴 건 진입 안 함 — 백과사전에 남을 뿐(카탈로그 안 넘침).
    stats: dict[str, UsageStat] = {}
    result = promote_candidates(
        stats, source_ids={"exa", "context7", "aws-mcp"}, catalog_ids=set()
    )
    assert result == []


def test_single_use_is_enough_threshold_one() -> None:
    # 문턱 1회: 딱 한 번 써도 진입(adopt의 3회와 다름 — 일부러 들인 번들 출신).
    stats = {"exa": _stat(count=1)}
    assert promote_candidates(stats, source_ids={"exa"}, catalog_ids=set()) == ["exa"]


def test_multiple_candidates_sorted() -> None:
    # 결정적 순서(정렬) — 보고·테스트 안정.
    stats = {"exa": _stat(), "aws-mcp": _stat(), "context7": _stat()}
    result = promote_candidates(
        stats, source_ids={"exa", "aws-mcp", "context7"}, catalog_ids=set()
    )
    assert result == ["aws-mcp", "context7", "exa"]
