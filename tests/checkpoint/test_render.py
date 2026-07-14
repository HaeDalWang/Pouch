"""체크포인트 규약 렌더링 검증 — 트리거·4슬롯·손잡이가 지침에 박히는지.

정책(스펙 §3·§4·§5·§7): 판단 위임 금지(관찰 가능한 사건으로만), 형식으로 장황함
차단(4슬롯), 손잡이 매번 부착. structural constraint > documentation promise.

  ① 앵커 있으면 목표를 박고, ◆목표에 그대로 쓰라 지시(재서술 금지)
  ② 앵커 없으면 checkpoint set으로 고정하라 안내
  ③ 트리거 3종(택1·재계획·계획밖)이 모두 들어간다
  ④ 4슬롯(◆) 마커·형식이 들어간다
  ⑤ 손잡이 문구가 들어가고, "멈추지 않는다"가 명시된다
"""

from __future__ import annotations

from pouch.checkpoint.anchor import Anchor
from pouch.checkpoint.render import HANDLE, render_checkpoint_protocol


def _joined(anchor: Anchor | None) -> str:
    return "\n".join(render_checkpoint_protocol(anchor))


def test_contract1_anchor_goal_pinned_verbatim() -> None:
    out = _joined(Anchor(goal="정렬 체크포인트 구현", set_at="2026-07-14T15:00:00"))

    assert "정렬 체크포인트 구현" in out
    # ◆목표 슬롯에 그대로 넣으라는 재서술 금지 지시
    assert "그대로" in out
    assert "다시 쓰지" in out or "재서술" in out


def test_contract2_no_anchor_guides_set() -> None:
    out = _joined(None)

    assert "아직 없음" in out
    assert "checkpoint set" in out


def test_contract3_all_three_triggers_present() -> None:
    out = _joined(None)

    assert "택1" in out
    assert "재계획" in out
    assert "계획 밖 행동" in out
    # 판단어 대신 사건으로 — "감 판단 금지"가 명시된다
    assert "판단 금지" in out


def test_contract4_four_slots_present() -> None:
    out = _joined(Anchor(goal="목표", set_at="2026-07-14T00:00:00"))

    assert "◆ 목표:" in out
    assert "◆ 했다/못했다:" in out
    assert "◆ 남은 것:" in out
    assert "◆ 새 분기:" in out


def test_contract4b_anchor_goal_prefilled_in_slot() -> None:
    # 앵커가 있으면 ◆목표 슬롯 예시에 목표가 미리 채워진다(그대로 재사용 유도)
    out = _joined(Anchor(goal="my-goal-xyz", set_at="2026-07-14T00:00:00"))

    assert "◆ 목표: my-goal-xyz" in out


def test_contract5_handle_and_no_stop() -> None:
    out = _joined(None)

    assert HANDLE in out
    assert "↳" in HANDLE
    # 손잡이는 작업을 멈추지 않는다는 명시
    assert "멈추지 않는다" in out
    assert "승인을 기다리지" in out
