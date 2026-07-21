"""훑은 적 있나 표식 — 이미 쓰던 사람에게 딱 한 번 알려주기 위한 근거.

init은 처음 한 번만 도니까, 이미 pouch를 쓰던 사람은 훑기가 생겨도 저절로
돌지 않는다. 그 사람이 "명령어를 알아야만 하는 사람"이 되지 않도록 상태
화면이 한 번 알려준다 — 그 판단 근거가 이 표식이다(배승도 선택 1, 2026-07-21).
"""

from __future__ import annotations

from pouch.catalog.sweep import has_swept, record_swept

_NOW = "2026-07-21T10:00:00"


def test_a_fresh_pouch_has_never_swept() -> None:
    assert has_swept() is False


def test_recording_a_sweep_flips_the_marker() -> None:
    record_swept(now=_NOW)

    assert has_swept() is True


def test_marker_survives_a_second_sweep() -> None:
    record_swept(now=_NOW)
    record_swept(now="2026-07-22T10:00:00")

    assert has_swept() is True


def test_marker_is_not_confused_by_a_broken_file() -> None:
    """표식 파일이 깨져 있어도 터지지 않는다 — 안 훑은 것으로 본다(안전한 쪽)."""
    from pouch import paths

    path = paths.sweep_marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{망가진 json", encoding="utf-8")

    assert has_swept() is False
