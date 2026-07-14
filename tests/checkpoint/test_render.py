"""체크포인트 규약 렌더링 검증 — 트리거·4슬롯·손잡이·마커가 지침에 박히는지.

정책(스펙 §3·§4·§5·§7 + v2 언어 규칙): 판단 위임 금지(관찰 가능한 사건으로만),
형식으로 장황함 차단(4슬롯), 손잡이 매번 부착. structural constraint >
documentation promise.

v2: 지침·슬롯 라벨(GOAL/DONE/NOT/LEFT/BRANCH)·블록 마커(⟦ALIGN⟧·◆·↳)는 영어/ASCII,
에이전트가 채워 사용자에게 보이는 값(앵커 목표)과 손잡이 문구는 한글.

  ① 앵커 있으면 목표(한글)를 박고, GOAL 슬롯에 그대로 쓰라 지시(재서술 금지, 영어)
  ② 앵커 없으면 checkpoint set으로 고정하라 안내(영어)
  ③ 트리거 3종(Pick-one·Replan·Off-plan)이 모두 들어간다(영어)
  ④ ⟦ALIGN⟧ 블록 마커 + 4슬롯(◆) 라벨(영어)이 들어간다
  ⑤ 손잡이 문구(한글)가 블록 안에 들어가고, "do NOT stop"이 명시된다
"""

from __future__ import annotations

from pouch.checkpoint.anchor import Anchor
from pouch.checkpoint.render import HANDLE, render_checkpoint_protocol


def _joined(anchor: Anchor | None) -> str:
    return "\n".join(render_checkpoint_protocol(anchor))


def test_contract1_anchor_goal_pinned_verbatim() -> None:
    out = _joined(Anchor(goal="정렬 체크포인트 구현", set_at="2026-07-14T15:00:00"))

    # 값(목표)은 한글 그대로
    assert "정렬 체크포인트 구현" in out
    # GOAL 슬롯에 그대로 넣으라는 재서술 금지 지시(영어)
    assert "verbatim" in out
    assert "never rewrite" in out


def test_contract2_no_anchor_guides_set() -> None:
    out = _joined(None)

    assert "none yet" in out
    assert "pouch checkpoint set" in out


def test_contract3_all_three_triggers_present() -> None:
    out = _joined(None)

    assert "Pick-one" in out
    assert "Replan" in out
    assert "Off-plan" in out
    # 판단어 대신 사건으로 — "Do NOT judge by feel"이 명시된다
    assert "Do NOT" in out
    assert "by feel" in out


def test_contract4_align_markers_and_four_slots_present() -> None:
    out = _joined(Anchor(goal="목표", set_at="2026-07-14T00:00:00"))

    # 블록 마커(Phase-2 훅 앵커)
    assert "⟦ALIGN⟧" in out
    assert "⟦/ALIGN⟧" in out
    # 4슬롯 라벨(영어)
    assert "◆ GOAL:" in out
    assert "◆ DONE/NOT:" in out
    assert "◆ LEFT:" in out
    assert "◆ BRANCH:" in out


def test_contract4b_anchor_goal_prefilled_in_slot() -> None:
    # 앵커가 있으면 ◆ GOAL 슬롯에 목표(한글)가 미리 채워진다(그대로 재사용 유도)
    out = _joined(Anchor(goal="my-goal-xyz", set_at="2026-07-14T00:00:00"))

    assert "◆ GOAL: my-goal-xyz" in out


def test_contract5_handle_and_no_stop() -> None:
    out = _joined(None)

    # 손잡이 문구는 한글, 블록 안에 들어간다
    assert HANDLE in out
    assert "↳" in HANDLE
    # 손잡이는 작업을 멈추지 않는다는 명시(영어)
    assert "do NOT stop" in out
    assert "without approval" in out or "Do not wait for approval" in out


def test_handle_sits_inside_align_block_after_branch() -> None:
    # 손잡이는 ⟦ALIGN⟧…⟦/ALIGN⟧ 안, ◆ BRANCH 다음·닫는 마커 앞에 온다(Phase-2 계약)
    out = _joined(None)

    open_idx = out.index("⟦ALIGN⟧")
    branch_idx = out.index("◆ BRANCH:", open_idx)
    handle_idx = out.index(HANDLE, open_idx)
    close_idx = out.index("⟦/ALIGN⟧", open_idx)

    assert branch_idx < handle_idx < close_idx
