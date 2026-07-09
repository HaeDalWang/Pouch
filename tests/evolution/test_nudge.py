"""쪽지 렌더링 계약 검증 — 못 넘던 발견 단계를 조르지 않고 심는 안내판.

정책([[pouch-proactive-nudge-policy]] 조각 3): 쪽지 심기 = SessionStart 조건부
주입(문턱 넘을 때만) + 당기는 말("…'정리하자' 하시면 도울게요"). 말만 심고 답을
조르지 않는다 — 쪽지 스스로 명령어 입구를 알려주는 안내판이 된다.

핵심 절제(수정3): 당김("정리하자")="볼게"지 "해"가 아니다. 쪽지는 자동 실행을
약속하지 않고, "목록 보여드리고 함께"라는 두 단계 동의를 예고한다.

  ① 문턱 미달(쌓인 것 0) → 빈 문자열(글자 0 침묵, note_zone이 안 그림)
  ② 쌓인 게 있으면 당기는 말 "정리하자"를 품는다(안내판)
  ③ 크기 힌트만 준다(목록 전체를 쏟지 않음 — 말만 심기)
  ④ 자동 실행을 약속하지 않는다("볼게"지 "해" 아님 — 목록 보여줌을 예고)
  ⑤ 순수 함수 — 같은 입력 같은 출력, 시계·IO 없음
"""

from __future__ import annotations

from pouch.evolution.nudge import NudgeSummary, render_note


def test_contract1_below_threshold_is_empty() -> None:
    empty = NudgeSummary(drop_count=0, reattach_count=0, adopt_count=0, memory_count=0)

    assert render_note(empty) == ""


def test_contract2_has_pulling_phrase() -> None:
    summary = NudgeSummary(drop_count=2, reattach_count=0, adopt_count=0, memory_count=0)

    note = render_note(summary)

    # 당기는 말이 쪽지 안에 있어 명령어 입구를 알려준다(안내판)
    assert "정리하자" in note


def test_contract3_gives_magnitude_not_full_list() -> None:
    summary = NudgeSummary(drop_count=3, reattach_count=1, adopt_count=2, memory_count=4)

    note = render_note(summary)

    # 크기 힌트(숫자)는 있되, 개별 항목 이름은 쏟지 않는다(말만 심기)
    assert "3" in note  # 내릴 것 개수
    assert len(note.splitlines()) <= 3  # 두어 줄 안내판, 목록 아님


def test_contract4_does_not_promise_auto_action() -> None:
    summary = NudgeSummary(drop_count=5, reattach_count=0, adopt_count=0, memory_count=0)

    note = render_note(summary)

    # "볼게"지 "해"가 아님 — 완료·자동 실행을 약속하지 않는다
    assert "정리했" not in note  # 이미 했다는 표현 금지
    assert "목록" in note or "보여" in note  # 두 단계(먼저 보여줌)를 예고


def test_contract5_render_is_pure() -> None:
    summary = NudgeSummary(drop_count=1, reattach_count=0, adopt_count=0, memory_count=0)

    assert render_note(summary) == render_note(summary)


def test_only_nonzero_kinds_appear() -> None:
    # 0인 종류는 쪽지에 언급되지 않는다(불필요한 소음 제거)
    only_memory = NudgeSummary(
        drop_count=0, reattach_count=0, adopt_count=0, memory_count=2
    )

    note = render_note(only_memory)

    assert "기억" in note
    assert "내릴" not in note  # drop이 0이면 언급 안 함
