"""체크포인트 규약 렌더링 — SessionStart 통로에 얹을 "정렬 확인" 지침 블록.

이 블록은 boundary 옆 고정 구역(반드시 읽음)에 주입된다. 에이전트에게 "언제
요약하고, 어떤 형식으로, 무엇을 붙일지"를 심는다. 판단 위임을 피하려 발동 조건을
관찰 가능한 사건으로만 정의하고(트리거), 장황함이 들어올 공간을 형식(4슬롯)으로
구조적으로 막는다(structural constraint > documentation promise).

손잡이(§5)는 훅으로 강제하지 않는다 — Claude Code에 "요약 뱉은 직후" 이벤트가
없고, 손잡이는 요약 밑 한 줄이라 제일 쉬운 부분이라, 이 주입 지침이 붙이게 한다.
"""

from __future__ import annotations

from pouch.checkpoint.anchor import Anchor

# 손잡이 문구 — 요약 뒤에 매번 붙는다. 흐름은 안 끊고 개입 여지만 남기는 절충.
HANDLE = "↳ (이대로 계속 감. 방향 틀렸으면 지금 말해)"


def render_checkpoint_protocol(anchor: Anchor | None) -> list[str]:
    """체크포인트 규약 블록을 마크다운 줄 리스트로 만든다.

    앵커가 있으면 현재 목표를 박고, 없으면 작업 시작에 목표를 고정하라 안내한다.
    반환은 줄 리스트 — render_context가 다른 구역과 함께 join한다.
    """
    lines = [
        "## 🎯 정렬 체크포인트 — 갈림길에서 방향 맞추기",
        "",
    ]
    lines.extend(_render_goal(anchor))
    lines.extend(_render_triggers())
    lines.extend(_render_format(anchor))
    lines.extend(_render_handle())
    return lines


def _render_goal(anchor: Anchor | None) -> list[str]:
    """현재 앵커(이번 목표)를 박거나, 없으면 고정 안내."""
    if anchor is not None:
        return [
            f"**이번 목표(앵커):** {anchor.goal}",
            "이 목표는 고정점이다. 아래 ◆목표 슬롯에 이 문장을 **그대로** 넣어라 "
            "— 절대 네 말로 다시 쓰지 마라(재서술하는 순간 정렬이 깨진다).",
            "",
        ]
    return [
        "**이번 목표(앵커):** 아직 없음.",
        "작업을 시작하면 사용자의 첫 지시에서 목표 한 줄을 뽑아 "
        "`pouch checkpoint set \"<한 줄 목표>\"`로 고정하라. 이후 요약의 ◆목표 "
        "슬롯은 `pouch checkpoint show` 값을 그대로 재사용한다.",
        "",
    ]


def _render_triggers() -> list[str]:
    """트리거 3종 — 판단어 금지, 관찰 가능한 사건으로만(§3)."""
    return [
        "**언제 요약하나 (아래 사건이 일어나면. \"중요한가?\" 같은 감 판단 금지):**",
        "1. **택1** — 두 갈래 이상 중 하나를 골라 진행할 때 (A안 vs B안)",
        "2. **재계획** — 앞 스텝 결과를 보고 원래 계획을 바꿀 때",
        "3. **계획 밖 행동 시작** — 원래 안 하려던 걸 새로 시작할 때 "
        "(계획에 없던 파일·도구·경로)",
        "",
        "되돌리기 비싼 짓(삭제·배포·외부 호출)은 기존 확인 절차가 이미 잡으므로 "
        "여기서 중복하지 않는다.",
        "",
    ]


def _render_format(anchor: Anchor | None) -> list[str]:
    """4슬롯 형식 — 각 한 줄, 형용사·추상어 금지(§4)."""
    goal_slot = anchor.goal if anchor is not None else "<앵커 목표 그대로>"
    return [
        "**요약 형식 (정확히 이 4슬롯. 각 한 줄. 형용사·추상어 금지):**",
        "```",
        f"◆ 목표: {goal_slot}",
        "◆ 했다/못했다: <완료·미완료만>",
        "◆ 남은 것: <한 줄>",
        "◆ 새 분기: <있으면 한 줄 / 없으면 \"없음\">",
        "```",
        "각 슬롯 한 줄. 두 줄 이상이거나 초등학생이 못 읽을 단어가 들어가면 형식 "
        "위반이다.",
        "",
    ]


def _render_handle() -> list[str]:
    """손잡이 부착 지시 + 멈추지 않음 명시(§5)."""
    return [
        "**요약 바로 뒤에 이 손잡이 한 줄을 매번 붙여라:**",
        "```",
        HANDLE,
        "```",
        "손잡이는 작업을 **멈추지 않는다** — 진행은 계속되고, 손잡이는 \"지금 "
        "개입 가능\"을 알리는 표식일 뿐이다. 승인을 기다리지 마라.",
        "",
    ]
