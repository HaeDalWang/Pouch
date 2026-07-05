"""reference 생존성 판정 — upstream 증발(rehome)의 기억판.

L1 body 안의 http(s) URL을 인식한다
L2 body 안의 로컬 경로를 인식한다(URL 없을 때)
L3 인식할 자원이 없으면 None — 판단 불가는 죽었다고 못 잖는다
L4 로컬 경로가 실존하면 살아있다
L5 로컬 경로가 없으면 죽었다
L6 URL은 주입된 http_head로 판정한다(실제 네트워크 없이 테스트)
L7 자원을 못 찾으면 살아있다고 본다(오탐 방지 — 판단 불가 ≠ 죽음)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pouch.memory.liveness import check_reference_alive, extract_resource
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


def _ref(body: str) -> MemoryEntry:
    return MemoryEntry(
        name="dashboard", description="d", body=body,
        type=MemoryType.REFERENCE, scope=MemoryScope.GLOBAL,
        created=date(2026, 1, 1),
    )


def test_l1_extracts_https_url() -> None:
    assert extract_resource("대시보드: https://grafana.internal/d/api 참고") == "https://grafana.internal/d/api"


def test_l2_extracts_local_path_when_no_url() -> None:
    assert extract_resource("경로: /Users/me/notes.md 참고") == "/Users/me/notes.md"


def test_l3_no_resource_returns_none() -> None:
    assert extract_resource("그냥 자연어 설명일 뿐") is None


def test_l4_existing_local_path_is_alive(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    target.write_text("x", encoding="utf-8")

    assert check_reference_alive(_ref(f"참고: {target}")) is True


def test_l5_missing_local_path_is_dead(tmp_path: Path) -> None:
    ghost = tmp_path / "ghost.md"

    assert check_reference_alive(_ref(f"참고: {ghost}")) is False


def test_l6_url_liveness_uses_injected_predicate() -> None:
    entry = _ref("https://example.test/dashboard")

    assert check_reference_alive(entry, http_head=lambda _url: True) is True
    assert check_reference_alive(entry, http_head=lambda _url: False) is False


def test_l7_unrecognizable_body_assumed_alive() -> None:
    assert check_reference_alive(_ref("링크 없는 그냥 메모")) is True
