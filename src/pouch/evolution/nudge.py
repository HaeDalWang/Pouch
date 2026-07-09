"""쪽지 렌더링 — 못 넘던 발견 단계를 조르지 않고 심는 안내판. 순수 함수.

정책([[pouch-proactive-nudge-policy]] 조각 3): 말만 심고 답을 조르지 않는다.
쪽지 스스로 당기는 말("…'정리하자' 하시면")을 품어 명령어 입구를 알려주는
안내판이 된다 — 못 넘던 발견 단계(있는 줄 알기·쓸 때인 줄 알기)를 조르지 않고
넘게 한다.

절제(수정3): 당김="볼게"지 "해"가 아니다. 쪽지는 자동 실행을 약속하지 않고
"목록부터 보여드릴게요"라는 두 단계 동의를 예고한다. 그리고 말만 심기 —
개별 항목 이름을 쏟지 않고 크기 힌트(개수)만 준다.

쪽지 구역 배선(note_zone)은 조각 4(물러남)와 함께 한다 — 물러남 없이 라이브로
심으면 매 세션 같은 쪽지가 반복돼 "절대 조르지 않는다" 불변식을 깬다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NudgeSummary:
    """쪽지에 담을 크기 힌트 — 종류별 개수만(목록 아님)."""

    drop_count: int  # 표면에서 내릴 후보
    reattach_count: int  # 다시 올릴 후보
    adopt_count: int  # 편입 안내 후보
    memory_count: int  # 확인·정리할 기억(pending+hygiene)

    @property
    def total(self) -> int:
        return (
            self.drop_count
            + self.reattach_count
            + self.adopt_count
            + self.memory_count
        )


def render_note(summary: NudgeSummary) -> str:
    """쪽지 텍스트를 만든다. 쌓인 게 없으면 빈 문자열(글자 0 침묵).

    0인 종류는 언급하지 않는다(불필요한 소음 제거). 두어 줄 안내판이지
    목록이 아니다 — 개별 항목 이름은 여기 없다.
    """
    if summary.total == 0:
        return ""

    # 0이 아닌 종류만 크기 힌트로 나열한다(말만 심기 — 이름은 안 쏟음).
    fragments: list[str] = []
    if summary.drop_count:
        fragments.append(f"내릴 도구 {summary.drop_count}개")
    if summary.reattach_count:
        fragments.append(f"다시 올릴 것 {summary.reattach_count}개")
    if summary.adopt_count:
        fragments.append(f"편입 후보 {summary.adopt_count}개")
    if summary.memory_count:
        fragments.append(f"확인할 기억 {summary.memory_count}개")

    listing = "·".join(fragments)
    # 당기는 말("정리하자")로 명령어 입구를 알려주고, "목록부터 보여드릴게요"로
    # 두 단계 동의를 예고한다("볼게"지 "해"가 아님 — 자동 실행 약속 없음).
    return (
        f"🦦 정리할 게 쌓였어요 — {listing}.\n"
        "하던 일 끝나고 '정리하자' 하시면 목록부터 보여드릴게요."
    )
