"""drop gate 검증 — 도구를 내릴 때 그 도구 출신 boundary를 방향으로 가른다.

P1의 마지막 조각. 안전 비대칭이 방향에 걸린다:
  - allow      : 도구와 함께 내려간다(허용은 좁게 — 도구 없이 떠도는 허용이 위험)
  - ask/deny   : 잔존 + 경고(금지·확인은 넓게 — 사라지는 게 위험)
  - 방향 불명   : 잔존(안전 쪽)
사람이 직접 건 boundary(source=user)는 방향 무관하게 gate가 건드리지 않는다.
"""

from __future__ import annotations

from datetime import date

from pouch.catalog.boundary import plan_boundary_drop
from pouch.memory.model import Direction, MemoryEntry, MemoryScope, MemoryType


def _boundary(
    name: str, direction: Direction | None, source: str
) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=f"{name} 경계",
        body="본문",
        type=MemoryType.BOUNDARY,
        scope=MemoryScope.GLOBAL,
        direction=direction,
        source=source,
        created=date(2026, 7, 7),
    )


def test_allow_from_dropped_tool_is_demoted() -> None:
    mems = [_boundary("dev-auto", Direction.ALLOW, "vendored:aws-cdk")]

    plan = plan_boundary_drop(mems, "aws-cdk")

    assert [m.name for m in plan.to_demote] == ["dev-auto"]
    assert plan.to_keep == ()


def test_ask_and_deny_from_dropped_tool_are_kept_with_warning() -> None:
    mems = [
        _boundary("prod-gate", Direction.ASK, "vendored:aws-cdk"),
        _boundary("no-destroy", Direction.DENY, "vendored:aws-cdk"),
    ]

    plan = plan_boundary_drop(mems, "aws-cdk")

    assert {m.name for m in plan.to_keep} == {"prod-gate", "no-destroy"}
    assert plan.to_demote == ()


def test_user_source_never_touched_even_if_allow() -> None:
    # 사람이 직접 건 것은 방향이 allow여도 gate가 건드리지 않는다(무조건 잔존).
    mems = [_boundary("my-rule", Direction.ALLOW, "user")]

    plan = plan_boundary_drop(mems, "aws-cdk")

    assert plan.to_demote == ()
    assert plan.to_keep == ()  # 아예 gate 대상이 아니다


def test_other_tools_boundaries_untouched() -> None:
    # 다른 도구가 딸고 온 boundary는 이 도구 drop과 무관하다.
    mems = [_boundary("s3-gate", Direction.ALLOW, "vendored:aws-s3")]

    plan = plan_boundary_drop(mems, "aws-cdk")

    assert plan.to_demote == ()
    assert plan.to_keep == ()


def test_unknown_direction_from_dropped_tool_is_kept() -> None:
    # 방향 불명(옛 데이터)은 안전 쪽 — 잔존시킨다.
    mems = [_boundary("vague", None, "vendored:aws-cdk")]

    plan = plan_boundary_drop(mems, "aws-cdk")

    assert {m.name for m in plan.to_keep} == {"vague"}
    assert plan.to_demote == ()
