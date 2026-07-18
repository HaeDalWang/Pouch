"""물어보기 안전판 — 한글 입력기 문자가 섞여도 죽지 않고 되묻는다.

실사용에서 잡힌 사고(2026-07-18): `Y` 뒤에 전각 공백이 섞이자 typer.confirm이
UnicodeDecodeError로 즉사. 사용자 잘못이 아니라 입력기의 자연스러운 흔적이므로,
pouch는 죽는 대신 되묻고 — 계속 못 읽으면 안전한 쪽(아니오)으로 접는다.
"""

from __future__ import annotations

from pouch.confirm import confirm


def _boom() -> UnicodeDecodeError:
    return UnicodeDecodeError("utf-8", b"\xe3", 0, 1, "invalid continuation byte")


def test_confirm_retries_once_after_unicode_error(monkeypatch) -> None:
    calls = {"count": 0}

    def flaky(message: str, default: bool = False) -> bool:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _boom()
        return True

    monkeypatch.setattr("pouch.confirm.typer.confirm", flaky)

    assert confirm("계속할까요?", default=True) is True
    assert calls["count"] == 2  # 한 번 되물었다


def test_confirm_folds_to_no_after_repeated_errors(monkeypatch) -> None:
    def always_broken(message: str, default: bool = False) -> bool:
        raise _boom()

    monkeypatch.setattr("pouch.confirm.typer.confirm", always_broken)

    # 스트림 자체가 깨졌으면 아니오로 접는다 — 동의 없인 아무것도 안 움직인다.
    assert confirm("계속할까요?", default=True) is False
