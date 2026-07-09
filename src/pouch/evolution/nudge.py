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
from datetime import datetime

_DEFAULT_BASE_INTERVAL_DAYS = 3  # 문턱 넘은 뒤 같은 쪽지 최소 간격
_DEFAULT_MAX_INTERVAL_DAYS = 30  # 물러남이 수렴하는 바닥 빈도(멈춤 아님)


@dataclass(frozen=True)
class NudgePolicy:
    """쪽지 간격 정책 — 매직넘버 회피, 기본값 있는 config.

    base_interval_days: 한 번 심은 뒤 다음까지 최소 침묵(간격 방어).
    max_interval_days: 물러남이 수렴하는 상한 — 무시가 쌓여도 완전히 멈추진
        않고 아주 드물게만 뜬다(담을 게 의미 있게 더 쌓이면 다시 심는 건 별개).
    """

    base_interval_days: int = _DEFAULT_BASE_INTERVAL_DAYS
    max_interval_days: int = _DEFAULT_MAX_INTERVAL_DAYS


def backoff_days(shown_count: int, policy: NudgePolicy) -> int:
    """지금까지 shown_count번 심었을 때 다음 쪽지까지의 간격(일).

    물러남 불변식(키우기 금지): shown_count가 커질수록 간격은 커지기만 한다
    (단조 비감소). 지수 backoff(심을수록 배로 뜸해짐)에 상한을 씌운다 — 무시가
    쌓이면 pouch는 점점 더 조용해지되, 상한에서 멈춰 바닥 빈도로 수렴한다.
    """
    if shown_count <= 0:
        return policy.base_interval_days
    raw = policy.base_interval_days * (2 ** (shown_count - 1))
    return min(raw, policy.max_interval_days)


def should_nudge(
    *,
    last_shown: str | None,
    shown_count: int,
    now: str,
    policy: NudgePolicy,
) -> bool:
    """지금 이 쪽지를 심어도 되는가 — 간격·물러남을 장부 위에서 판정한다.

    심은 적 없으면(last_shown None) 보인다(문턱은 호출부가 이미 확인). 심은
    적 있으면 backoff 간격이 지났을 때만 다시 보인다 — 많이 무시할수록(count
    큼) 더 오래 침묵한다. 시계는 주입한다(결정적).
    """
    if last_shown is None:
        return True
    elapsed = _days_between(last_shown, now)
    return elapsed >= backoff_days(shown_count, policy)


def _days_between(earlier: str, later: str) -> float:
    """ISO8601 두 시각 사이 일수. earlier가 미래면 음수."""
    delta = datetime.fromisoformat(later) - datetime.fromisoformat(earlier)
    return delta.total_seconds() / 86400


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


def plan_nudge(
    summary: NudgeSummary,
    *,
    last_shown: str | None,
    shown_count: int,
    now: str,
    policy: NudgePolicy,
) -> str:
    """문턱·간격·물러남을 모두 통과하면 쪽지 텍스트, 아니면 ""(침묵). 순수 함수.

    잔소리 방어 4개가 한 곳에 모인다: 문턱(summary.total==0이면 침묵)·간격/묵히기/
    물러남(should_nudge가 backoff로 판정)·기본은 침묵(둘 중 하나라도 미달이면 "").
    이걸 통과해 텍스트가 나오면, 호출부(CLI 경계)가 장부에 record_shown 한다.
    """
    if summary.total == 0:  # 문턱 미달 — 쌓인 게 없음
        return ""
    if not should_nudge(
        last_shown=last_shown, shown_count=shown_count, now=now, policy=policy
    ):
        return ""  # 간격·물러남 미달 — 안 조름
    return render_note(summary)
