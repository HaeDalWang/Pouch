"""주입 통로 구역 분리 계약 검증 — 고정 구역(반드시 읽음) vs 쪽지 구역(무시 가능).

정책([[pouch-proactive-nudge-policy]], 조각 3 하드 선행 조건): 쪽지는 boundary와
같은 SessionStart 통로에 얹히는데, 그대로 섞으면 churn하는 쪽지가 boundary 주의력을
희석한다. 같은 통로, 구역만 가른다. 가르는 진짜 축 = churn이 아니라 "반드시 읽어야
함 vs 무시돼도 됨".

  고정 구역(최상단): boundary([DENY])+기억 인덱스. 반드시 읽음. 실패는 시끄럽게.
  쪽지 구역(하단, 조건부): 제안 쪽지. 무시돼도 됨. 문턱 아래면 글자 0.

불변식(한 구현으로 ①+③ 동시 만족 — 고정 먼저 렌더, 쪽지는 격리 시도):
  ① 쪽지가 아무리 많아도 boundary 구역보다 위로 못 온다.
  ② 문턱 미달(쪽지 빈 내용) → 쪽지 구역 = 빈 문자열(구분선·헤더조차 없음).
  ③ 쪽지 렌더링 실패 → 고정 구역은 그대로 나온다(격리). 비대칭: 고정 구역
     실패 → 쪽지만 성공해 나가는 건 막는다(가드레일 없는 제안-only는 차단보다 위험).
"""

from __future__ import annotations

from datetime import date

import pytest

from pouch.memory.context import render_session_context
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


def _boundary(name: str = "auto-commit") -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=f"{name} 경계",
        body="force push 금지",
        type=MemoryType.BOUNDARY,
        scope=MemoryScope.PROJECT,
        created=date(2026, 7, 9),
    )


def test_contract1_note_zone_stays_below_boundary() -> None:
    out = render_session_context(
        [_boundary()], note_zone=lambda: "🦦 정리할 게 쌓였어요"
    )

    # 쪽지가 boundary 구역보다 아래
    assert "Autonomy Boundaries" in out
    assert "🦦 정리할 게 쌓였어요" in out
    assert out.index("Autonomy Boundaries") < out.index("🦦 정리할 게 쌓였어요")


def test_contract2_below_threshold_is_truly_empty() -> None:
    # 쪽지 생산자가 빈 내용 → 쪽지 구역 자체가 안 그려짐(구분선·헤더조차 없음)
    with_note = render_session_context([_boundary()], note_zone=lambda: "content")
    without_note = render_session_context([_boundary()], note_zone=lambda: "")
    whitespace_only = render_session_context([_boundary()], note_zone=lambda: "   \n  ")

    # 문턱 미달이면 고정 구역만 남고, 쪽지 흔적(구분선)이 전혀 없다
    assert without_note == whitespace_only
    assert "---" not in without_note  # 구분선조차 없음
    assert "---" in with_note  # 내용 있을 때만 구분선 등장


def test_contract3a_note_failure_preserves_fixed_zone() -> None:
    def _boom() -> str:
        raise RuntimeError("쪽지 렌더링 터짐")

    # 쪽지가 터져도 고정 구역(boundary)은 그대로 나온다(격리)
    out = render_session_context([_boundary()], note_zone=_boom)

    assert "force push 금지" in out
    assert "Autonomy Boundaries" in out


def test_contract3b_fixed_failure_blocks_note_escape() -> None:
    def _bad_entries():
        raise RuntimeError("고정 구역 터짐")
        yield  # generator

    def _note() -> str:
        return "이 쪽지는 절대 혼자 나가면 안 된다"

    # 고정 구역이 터지면 전체가 시끄럽게 실패 — 쪽지만 성공해 나가지 못한다(비대칭)
    with pytest.raises(RuntimeError, match="고정 구역 터짐"):
        render_session_context(_bad_entries(), note_zone=_note)


def test_contract4_default_note_zone_is_silent() -> None:
    # 쪽지 생산자를 안 주면(현재 기본) 고정 구역만 — 쪽지 흔적(구분선) 없음
    out = render_session_context([_boundary()])

    assert "force push 금지" in out  # 고정 구역(boundary)은 나온다
    assert "---" not in out  # 쪽지 구역 흔적 없음


def test_checkpoint_protocol_always_in_fixed_zone() -> None:
    # 체크포인트 규약은 앵커·기억 유무와 무관하게 항상 고정 구역에 실린다(기능 핵심).
    from pouch.checkpoint.anchor import Anchor

    # 기억이 0개여도 규약은 주입된다
    empty = render_session_context([])
    assert "Alignment Checkpoint" in empty
    assert "◆ GOAL:" in empty

    # 앵커가 있으면 그 목표가 규약에 박힌다
    with_anchor = render_session_context(
        [], anchor=Anchor(goal="my-goal", set_at="2026-07-14T00:00:00")
    )
    assert "my-goal" in with_anchor


def test_checkpoint_below_boundary_above_memory() -> None:
    # 배치: 경계(안전 최우선) → 체크포인트 규약 → 기억 인덱스
    user = MemoryEntry(
        name="prefers-uv",
        description="파이썬은 uv",
        body="본문",
        type=MemoryType.USER,
        scope=MemoryScope.GLOBAL,
        created=date(2026, 7, 9),
    )
    out = render_session_context([_boundary(), user])

    assert out.index("Autonomy Boundaries") < out.index("Alignment Checkpoint")
    assert out.index("Alignment Checkpoint") < out.index("prefers-uv")


def test_checkpoint_note_failure_still_preserves_checkpoint() -> None:
    # 쪽지가 터져도 체크포인트 규약(고정 구역)은 그대로 나온다(격리)
    def _boom() -> str:
        raise RuntimeError("쪽지 터짐")

    out = render_session_context([], note_zone=_boom)
    assert "Alignment Checkpoint" in out
