"""결과 예고 — evolve 제안 항목마다 "효과 + 되돌리는 정확한 한 줄". 순수 함수.

정책([[pouch-proactive-nudge-policy]] 조각 2): 결과 예고는 에이전트가 지어내면
안 되고 pouch가 내놓은 걸 그대로 전달한다. evolve가 항목마다 효과와 되돌리는
정확한 명령을 구조적으로 뱉게 해, 에이전트가 이해를 건너뛸 수 *없게* 만든다
(결과 지어내기 금지 → 반드시 pouch에 물어봐야 함).

정직성 불변식: undo는 실재하는 CLI 명령이어야 한다. 되돌릴 게 없으면(안내만)
None — 없는 명령을 지어내면 그 지어내기를 pouch 안에 박는 꼴이라 원칙의 정반대.

사람용 rich 출력(commands.py)과 에이전트용 기계 출력(쪽지 통로)이 둘 다 이 한
구조에서 파생돼, 되돌림 명령의 단일 출처가 된다 — 산문 곳곳에 흩어지지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.evolution.attach import AttachCandidate
from pouch.evolution.candidates import DropCandidate


@dataclass(frozen=True)
class ChangePreview:
    """한 제안이 표면에 무슨 일을 하는지 + 정확히 어떻게 되돌리는지.

    undo가 None이면 "자동 실행이 없어 되돌릴 것도 없다"(안내만)는 뜻이지,
    "되돌리는 법을 모른다"가 아니다.
    """

    target: str  # 대상 entry_id
    action: str  # "drop" | "reattach" | "adopt" | "observe"
    effect: str  # 표면에서 무슨 일이 일어나는지 (사람 말)
    undo: str | None  # 되돌리는 정확한 CLI 한 줄, 없으면 None


def preview_drop(candidate: DropCandidate) -> ChangePreview:
    """drop 후보의 예고 — 표면에서 내려가고, catalog install로 되돌린다."""
    return ChangePreview(
        target=candidate.entry_id,
        action="drop",
        effect="활성 표면에서 내려갑니다(카탈로그·개인화는 그대로 남습니다).",
        undo=f"pouch catalog install {candidate.entry_id}",
    )


def preview_attach(candidate: AttachCandidate) -> ChangePreview:
    """attach 후보의 예고 — 종류에 따라 효과·되돌림이 다르다.

    reattach만 표면을 실제로 바꾼다(→ uninstall로 되돌림). adopt·observe는
    아무것도 자동 실행하지 않아 되돌릴 것이 없다(undo None, 정직성 불변식).
    """
    if candidate.kind == "reattach":
        return ChangePreview(
            target=candidate.entry_id,
            action="reattach",
            effect="표면에 다시 올라갑니다(개인화 overlay는 보존됩니다).",
            undo=f"pouch catalog uninstall {candidate.entry_id}",
        )
    if candidate.kind == "adopt":
        return ChangePreview(
            target=candidate.entry_id,
            action="adopt",
            effect="자동 편입은 없습니다 — pouch catalog import로 담을지 안내만 합니다.",
            undo=None,
        )
    # observe: 표면을 플러그인이 관리 — pouch에 통제권이 없어 관측만.
    return ChangePreview(
        target=candidate.entry_id,
        action="observe",
        effect="플러그인이 표면을 관리 중이라 관측만 합니다(pouch가 바꾸지 않습니다).",
        undo=None,
    )
