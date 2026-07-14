"""정렬 앵커 사이드카 계약 검증 — "이번 작업 목표"의 고정점.

정책(pouch-scope-boundary의 거울상): 작업 시작에 목표를 한 줄로 박아 ◆목표 슬롯이
재해석 없이 재사용할 고정점을 만든다. ledger.py와 같은 정신(버려도 되는 층, now 주입).

  ① set→load 왕복: 고정한 목표를 그대로 되읽는다
  ② set은 덮어쓴다(세션 개념 없음 → 매 작업 시작 재설정)
  ③ 파일 없으면 None(첫 실행 안전)
  ④ 빈/goal 없는 파일도 None(깨진 사이드카 안전)
  ⑤ clear: 지웠으면 True, 애초에 없으면 False
"""

from __future__ import annotations

from pathlib import Path

from pouch.checkpoint.anchor import clear_anchor, load_anchor, set_anchor


def test_contract1_set_then_load_roundtrip(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.json"

    set_anchor("정렬 체크포인트 구현", now="2026-07-14T15:00:00", anchor_path=anchor_path)

    loaded = load_anchor(anchor_path=anchor_path)
    assert loaded is not None
    assert loaded.goal == "정렬 체크포인트 구현"
    assert loaded.set_at == "2026-07-14T15:00:00"


def test_contract2_set_overwrites(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.json"
    set_anchor("첫 목표", now="2026-07-14T10:00:00", anchor_path=anchor_path)

    set_anchor("바뀐 목표", now="2026-07-14T12:00:00", anchor_path=anchor_path)

    loaded = load_anchor(anchor_path=anchor_path)
    assert loaded is not None
    assert loaded.goal == "바뀐 목표"
    assert loaded.set_at == "2026-07-14T12:00:00"


def test_contract3_missing_file_is_none(tmp_path: Path) -> None:
    assert load_anchor(anchor_path=tmp_path / "nope.json") is None


def test_contract4_empty_or_goalless_is_none(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("   \n", encoding="utf-8")
    assert load_anchor(anchor_path=empty) is None

    goalless = tmp_path / "goalless.json"
    goalless.write_text('{"set_at": "2026-07-14T00:00:00"}', encoding="utf-8")
    assert load_anchor(anchor_path=goalless) is None


def test_contract5_clear_reports_whether_removed(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.json"

    # 없을 때 clear → False
    assert clear_anchor(anchor_path=anchor_path) is False

    # 있을 때 clear → True, 이후 load는 None
    set_anchor("목표", now="2026-07-14T00:00:00", anchor_path=anchor_path)
    assert clear_anchor(anchor_path=anchor_path) is True
    assert load_anchor(anchor_path=anchor_path) is None
