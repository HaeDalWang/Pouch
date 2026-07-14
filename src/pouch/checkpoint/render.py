"""체크포인트 규약 렌더링 — SessionStart 통로에 얹을 "정렬 확인" 지침 블록.

이 블록은 boundary 옆 고정 구역(반드시 읽음)에 주입된다. 에이전트에게 "언제
요약하고, 어떤 형식으로, 무엇을 붙일지"를 심는다. 판단 위임을 피하려 발동 조건을
관찰 가능한 사건으로만 정의하고(트리거), 장황함이 들어올 공간을 형식(4슬롯)으로
구조적으로 막는다(structural constraint > documentation promise).

v2 언어 규칙: 에이전트가 읽는 지침·슬롯 라벨(GOAL/DONE/NOT/LEFT/BRANCH)·블록
마커(⟦ALIGN⟧·◆·↳)는 영어/ASCII다 — GPT·Gemini의 지침 준수가 더 안정적이고,
Phase-2 훅이 정규식으로 마커를 잡을 때 도구별 인코딩을 더 잘 견딘다. 반대로
에이전트가 채워 사용자에게 보이는 값(앵커 목표·요약 슬롯 내용)과 손잡이 문구는
한글이다 — 읽는 사람이 승도라 빠른 스캔이 목적이기 때문. 라벨은 기계를 위해,
값은 사람을 위해.

⟦ALIGN⟧…⟦/ALIGN⟧ 마커는 core/adapter 경계의 못이다. Phase-1은 이 블록을 지침으로만
전달하지만(약속 수준), Phase-2 훅이 이 마커로 블록을 찾아 손잡이 누락을 강제 부착한다
— 마커를 바꾸면 Phase-1 출력이 Phase-2에서 버려진다. 손잡이(§규칙)는 아직 훅으로
강제하지 않는다 — Claude Code에 "요약 뱉은 직후" 이벤트가 없어, 이 주입 지침이 붙이게 한다.
"""

from __future__ import annotations

from pouch.checkpoint.anchor import Anchor

# 손잡이 문구 — 요약 뒤에 매번 붙는다. 흐름은 안 끊고 개입 여지만 남기는 절충.
# 사용자(승도)가 요약과 함께 보는 출력이라 한글이다(라벨·마커는 영어여도 이 값은 한글).
HANDLE = "↳ (이대로 계속 감. 방향 틀렸으면 지금 말해)"


def render_checkpoint_protocol(anchor: Anchor | None) -> list[str]:
    """체크포인트 규약 블록을 마크다운 줄 리스트로 만든다.

    앵커가 있으면 현재 목표를 박고, 없으면 작업 시작에 목표를 고정하라 안내한다.
    반환은 줄 리스트 — render_context가 다른 구역과 함께 join한다.
    """
    lines = [
        "## Alignment Checkpoint",
        "",
        "Output language: write all FILLED-IN VALUES in Korean. Keep the labels "
        "and markers exactly as-is (English/ASCII). Do not switch the content to "
        "English just because the labels are English.",
        "",
    ]
    lines.extend(_render_goal(anchor))
    lines.extend(_render_triggers())
    lines.extend(_render_format(anchor))
    lines.extend(_render_rules())
    return lines


def _render_goal(anchor: Anchor | None) -> list[str]:
    """현재 앵커(이번 목표)를 박거나, 없으면 고정 안내. 목표 값 자체는 한글."""
    if anchor is not None:
        return [
            "### Goal anchor",
            f"**Current goal (anchor):** {anchor.goal}",
            "This anchor is the fixed point. Copy this sentence **verbatim** into "
            "the `◆ GOAL:` slot below — never rewrite it in your own words "
            "(the moment you re-summarize it, alignment breaks).",
            "",
        ]
    return [
        "### Goal anchor",
        "**Current goal (anchor):** none yet.",
        "When a task starts, compress the user's first instruction into one line "
        'and lock it with `pouch checkpoint set "<one-line goal>"`. Afterward the '
        "`◆ GOAL:` slot reuses the `pouch checkpoint show` value verbatim.",
        "",
    ]


def _render_triggers() -> list[str]:
    """트리거 3종 — 판단 위임 금지, 관찰 가능한 사건으로만."""
    return [
        "### When to summarize (triggers)",
        "Emit an alignment summary when **any** of these actually happens. Do NOT "
        'judge "is this important?" by feel — only check whether the observable '
        "event occurred:",
        "1. **Pick-one** — choosing one path among two or more to proceed (plan A vs B).",
        "2. **Replan** — changing the original plan based on a previous step's result.",
        "3. **Off-plan start** — starting something not in the original plan "
        "(a file / tool / path that wasn't planned).",
        "",
        "Hard-to-reverse actions (delete / deploy / external call) are already "
        "caught by the existing confirmation flow, so they are not duplicated here.",
        "",
    ]


def _render_format(anchor: Anchor | None) -> list[str]:
    """요약 형식 — ⟦ALIGN⟧ 블록으로 감싼 4슬롯. 라벨 영어, 값 한글."""
    goal_slot = anchor.goal if anchor is not None else "{the locked anchor, verbatim — in Korean}"
    return [
        "### Summary format (use EXACTLY this format)",
        "Emit the block below with **exactly** these markers and order. Each slot "
        "is **one line**, values in **Korean**. No adjectives, no abstractions. If "
        "a word would need study to read, it's a format violation.",
        "```",
        "⟦ALIGN⟧",
        f"◆ GOAL: {goal_slot}",
        "◆ DONE/NOT: {done vs not-done only — in Korean}",
        "◆ LEFT: {one line — in Korean}",
        '◆ BRANCH: {one line if any / "없음" if none}',
        HANDLE,
        "⟦/ALIGN⟧",
        "```",
        "",
    ]


def _render_rules() -> list[str]:
    """규칙 — 멈추지 않음·손잡이 매번·GOAL은 복사·마커 불변."""
    return [
        "### Rules",
        "- After emitting the summary, **do NOT stop.** Do not wait for approval; "
        "keep going.",
        f"- The `↳` handle line (`{HANDLE}`) is attached **every time**, inside the "
        "block right after `◆ BRANCH`. Not conditional — without it the summary is worthless.",
        "- The `◆ GOAL:` slot is a **copy** of the start-time anchor — never re-summarized.",
        "- Keep the `⟦ALIGN⟧` / `⟦/ALIGN⟧` markers and the `◆` `↳` symbols "
        "**unchanged** (a machine finds the block by these).",
        "- Labels (GOAL/DONE/NOT/LEFT/BRANCH) stay English; the text after each "
        "label is Korean.",
        "",
    ]
