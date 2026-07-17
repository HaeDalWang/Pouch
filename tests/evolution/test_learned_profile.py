"""학습된 관심사 — core 도구의 토큰을 관심사로 승격(순수)."""

from __future__ import annotations

from pouch.catalog.model import ToolEntry, ToolKind
from pouch.evolution.learned_profile import learned_interest_tokens, learned_interests
from pouch.evolution.usage_log import UsageEvent


def _uses(entry_id: str, count: int, first: str, last: str) -> list[UsageEvent]:
    """count개 이벤트 — first·last를 양끝으로, 나머지는 first에 쌓는다."""
    evs = [UsageEvent(entry_id=entry_id, ts=first), UsageEvent(entry_id=entry_id, ts=last)]
    evs += [UsageEvent(entry_id=entry_id, ts=first) for _ in range(max(0, count - 2))]
    return evs


def _entry(entry_id: str, description: str, *, tags: tuple[str, ...] = ()) -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id,
        kind=ToolKind.SKILL,
        source="test",
        title=entry_id,
        description=description,
        body="본문",
        tags=tags,
    )


# core를 만드는 사용: 12회 + span 30일(min_count 10·min_span 21 넘김).
_SUSTAINED = ("2026-06-01T00:00:00", "2026-07-01T00:00:00")
# burst: 12회지만 span 3일(지속 아님 → 비-core).
_BURST = ("2026-07-01T00:00:00", "2026-07-04T00:00:00")


def test_core_tool_tokens_become_interests() -> None:
    entries = [_entry("aws-deploy", "Deploy to AWS cloud infrastructure")]
    events = _uses("aws-deploy", 12, *_SUSTAINED)
    tokens = learned_interest_tokens(events, entries)
    # 설명·id에서 쪼갠 의미 토큰이 관심사로 승격("to"는 불용어라 pool이 뺌).
    assert {"aws", "deploy", "cloud", "infrastructure"} <= tokens
    assert "to" not in tokens


def test_burst_tool_is_not_promoted() -> None:
    entries = [_entry("aws-deploy", "Deploy to AWS cloud infrastructure")]
    events = _uses("aws-deploy", 12, *_BURST)  # 몰아쓰고 끝 → core 아님
    assert learned_interest_tokens(events, entries) == set()


def test_cold_start_no_core_is_empty() -> None:
    entries = [_entry("aws-deploy", "Deploy to AWS cloud infrastructure")]
    events = _uses("aws-deploy", 3, *_SUSTAINED)  # 5회 미만 → core 아님
    assert learned_interests(events, entries) == []
    assert learned_interest_tokens(events, entries) == set()


def test_shared_token_ranks_higher() -> None:
    # 두 core 도구가 'aws'를 공유 → 'aws'가 단독 토큰보다 위.
    entries = [
        _entry("aws-deploy", "Deploy to AWS"),
        _entry("aws-cost", "AWS billing report"),
    ]
    events = _uses("aws-deploy", 12, *_SUSTAINED) + _uses("aws-cost", 12, *_SUSTAINED)
    ranked = learned_interests(events, entries)
    assert ranked[0] == ("aws", 2)  # 두 도구 공유
    # 단독 토큰(deploy·billing·report)은 count 1.
    assert dict(ranked)["deploy"] == 1
    assert dict(ranked)["billing"] == 1


def test_non_core_tool_tokens_excluded() -> None:
    # core 하나 + burst 하나 → burst 도구의 고유 토큰은 관심사에 없다.
    entries = [
        _entry("aws-deploy", "Deploy to AWS"),
        _entry("gcp-tool", "Google Cloud Platform helper"),
    ]
    events = _uses("aws-deploy", 12, *_SUSTAINED) + _uses("gcp-tool", 12, *_BURST)
    tokens = learned_interest_tokens(events, entries)
    assert "aws" in tokens
    assert "google" not in tokens
    assert "platform" not in tokens


def test_core_outside_catalog_has_nothing_to_promote() -> None:
    # 많이·오래 썼지만 카탈로그에 엔트리가 없는 도구 → 승격할 토큰이 없다.
    entries = [_entry("aws-deploy", "Deploy to AWS")]
    events = _uses("aws-deploy", 12, *_SUSTAINED) + _uses("mystery", 12, *_SUSTAINED)
    tokens = learned_interest_tokens(events, entries)
    assert "aws" in tokens
    assert "mystery" not in tokens


def test_alias_folding_reaches_core_then_promotes() -> None:
    # 두 별칭이 각 6회(개별론 <10)지만 접으면 12회·span 김 → core → 승격.
    entries = [_entry("exa", "Web search retrieval")]
    events = _uses("exa", 6, "2026-06-01T00:00:00", "2026-06-20T00:00:00")
    events += _uses("plugin_x_exa", 6, "2026-06-25T00:00:00", "2026-07-05T00:00:00")
    without = learned_interest_tokens(events, entries)
    withmap = learned_interest_tokens(events, entries, alias_map={"plugin_x_exa": "exa"})
    assert without == set()  # 안 접으면 core 미달
    assert {"web", "search", "retrieval"} <= withmap
