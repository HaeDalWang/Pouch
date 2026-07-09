"""결과 예고 계약 검증 — evolve 제안 항목마다 "효과 + 되돌리는 정확한 한 줄".

정책([[pouch-proactive-nudge-policy]] 조각 2): 결과 예고는 에이전트가 지어내면
안 되고 pouch가 내놓은 걸 그대로 전달한다. 그래서 evolve가 항목마다 효과와
되돌리는 정확한 명령을 *구조적으로* 뱉어야 한다 — 이게 에이전트가 이해를
건너뛸 수 없게 만드는 자물쇠(결과 지어내기 금지라 반드시 pouch에 물어봐야 함).

정직성 불변식: undo는 실재하는 CLI 명령이어야 한다. 되돌릴 게 없으면(안내만)
None이지, 없는 명령을 지어내지 않는다 — 지어내기를 pouch 안에 박으면 원칙의 정반대.

  ① drop 예고: 표면에서 내려감(카탈로그·개인화 보존) + undo = catalog install
  ② reattach 예고: 표면에 다시 올림 + undo = catalog uninstall
  ③ adopt 예고: 자동 실행 없음(편입 안내만) → undo None
  ④ observe 예고: 관측만(표면 통제권 없음) → undo None
  ⑤ 순수 함수 — 시계·IO 없이 후보만으로 예고를 만든다
"""

from __future__ import annotations

from pouch.evolution.attach import AttachCandidate
from pouch.evolution.candidates import DropCandidate
from pouch.evolution.preview import (
    ChangePreview,
    preview_attach,
    preview_drop,
)


def test_contract1_drop_preview_has_install_undo() -> None:
    cand = DropCandidate("aws-iam", "never-used")

    preview = preview_drop(cand)

    assert isinstance(preview, ChangePreview)
    assert preview.target == "aws-iam"
    assert preview.action == "drop"
    # 되돌림은 실재하는 정확한 명령 (catalog install = 재부착의 공식 입구)
    assert preview.undo == "pouch catalog install aws-iam"
    # 효과는 "표면에서 내려가되 카탈로그·개인화는 남는다"를 담는다
    assert "표면" in preview.effect


def test_contract2_reattach_preview_has_uninstall_undo() -> None:
    cand = AttachCandidate("terraform", "reattach", count=3, last_used="2026-07-09T00:00:00")

    preview = preview_attach(cand)

    assert preview.target == "terraform"
    assert preview.action == "reattach"
    assert preview.undo == "pouch catalog uninstall terraform"
    assert "표면" in preview.effect


def test_contract3_adopt_preview_has_no_undo() -> None:
    cand = AttachCandidate("kubectl", "adopt", count=5, last_used="2026-07-09T00:00:00")

    preview = preview_attach(cand)

    assert preview.action == "adopt"
    # adopt는 아무것도 자동 실행하지 않는다(안내만) → 되돌릴 것이 없다
    assert preview.undo is None
    # 효과는 편입이 자동이 아님을 알린다
    assert "import" in preview.effect or "편입" in preview.effect


def test_contract4_observe_preview_has_no_undo() -> None:
    cand = AttachCandidate("plugin-srv", "observe", count=4, last_used="2026-07-09T00:00:00")

    preview = preview_attach(cand)

    assert preview.action == "observe"
    assert preview.undo is None
    assert "관측" in preview.effect


def test_contract5_preview_is_pure() -> None:
    # 같은 입력 → 같은 출력, 시계·IO 의존 없음
    cand = DropCandidate("a", "stale")

    assert preview_drop(cand) == preview_drop(cand)
