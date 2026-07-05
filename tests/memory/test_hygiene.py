"""나가는 문(위생) 계약 — 기억은 나이가 아니라 진실로 닳는다.

붕괴 신호는 타입별이다(나이는 project에만 통함):
  H1 project 만료 → 강등 후보(expired)
  H2 아직 안 낡은 project → 후보 아님
  H3 죽은 reference → 강등 후보(dead-reference)  ← upstream 증발의 기억판
  H4 살아있는 reference → 후보 아님
  H5 boundary는 제외 — 아무리 낡아도 후보 아님(안 걸린 deny=제 일 중)
  H6 feedback·user는 v0에서 나갈 문 없음(모순만이 신호인데 defer) — 인지된 갭
  H7 weight 면역 — 높으면 나이 기반 강등에서 빠짐
  H8 죽은 reference는 weight 높아도 후보 — 404는 weight로 못 살림
  H9 INDEXED만 대상 — pending(미확인)·archived(이미 강등)는 재제안 안 함
모두 제안만(아무것도 강등 안 함). 생존성 IO는 예측자로 주입해 함수는 순수하게 둔다.
"""

from __future__ import annotations

from datetime import date

from pouch.memory.hygiene import hygiene_candidates
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState, MemoryType

_NOW = date(2026, 7, 5)


def _entry(
    name: str,
    type: MemoryType,
    *,
    created: date = date(2026, 1, 1),
    weight: int = 0,
    state: MemoryState = MemoryState.INDEXED,
) -> MemoryEntry:
    return MemoryEntry(
        name=name, description=f"{name} 설명", body="본문",
        type=type, scope=MemoryScope.GLOBAL,
        weight=weight, created=created, state=state,
    )


def _all_alive(_: MemoryEntry) -> bool:
    return True


def _all_dead(_: MemoryEntry) -> bool:
    return False


def _names(candidates) -> list[str]:
    return [c.name for c in candidates]


def test_h1_expired_project_is_candidate() -> None:
    entries = [_entry("old-sprint", MemoryType.PROJECT, created=date(2026, 1, 1))]

    result = hygiene_candidates(entries, now=_NOW, is_alive=_all_alive)

    assert _names(result) == ["old-sprint"]
    assert result[0].reason == "expired"


def test_h2_fresh_project_is_not_candidate() -> None:
    entries = [_entry("this-week", MemoryType.PROJECT, created=date(2026, 7, 1))]

    assert hygiene_candidates(entries, now=_NOW, is_alive=_all_alive) == []


def test_h3_dead_reference_is_candidate() -> None:
    entries = [_entry("grafana", MemoryType.REFERENCE, created=date(2026, 7, 4))]

    result = hygiene_candidates(entries, now=_NOW, is_alive=_all_dead)

    assert _names(result) == ["grafana"]
    assert result[0].reason == "dead-reference"


def test_h4_live_reference_is_not_candidate() -> None:
    entries = [_entry("grafana", MemoryType.REFERENCE, created=date(2026, 1, 1))]

    assert hygiene_candidates(entries, now=_NOW, is_alive=_all_alive) == []


def test_h5_boundary_never_candidate_however_old() -> None:
    entries = [_entry("prod-gate", MemoryType.BOUNDARY, created=date(2025, 1, 1))]

    assert hygiene_candidates(entries, now=_NOW, is_alive=_all_dead) == []


def test_h6_feedback_and_user_have_no_v0_door() -> None:
    # 인지된 갭: 모순만이 신호인데 v0에서 defer라 나갈 문이 없다.
    entries = [
        _entry("stale-feedback", MemoryType.FEEDBACK, created=date(2025, 1, 1)),
        _entry("old-pref", MemoryType.USER, created=date(2025, 1, 1)),
    ]

    assert hygiene_candidates(entries, now=_NOW, is_alive=_all_dead) == []


def test_h7_high_weight_immune_from_expiry() -> None:
    entries = [
        _entry("pinned", MemoryType.PROJECT, created=date(2026, 1, 1), weight=5)
    ]

    assert hygiene_candidates(entries, now=_NOW, is_alive=_all_alive) == []


def test_h8_dead_reference_not_immunized_by_weight() -> None:
    # 나이 면역과 달리 생존성은 weight로 못 덮는다 — 죽은 자원은 죽었다.
    entries = [
        _entry("pinned-dash", MemoryType.REFERENCE, created=date(2026, 1, 1), weight=9)
    ]

    result = hygiene_candidates(entries, now=_NOW, is_alive=_all_dead)

    assert _names(result) == ["pinned-dash"]


def test_h9_only_indexed_tier_is_swept() -> None:
    entries = [
        _entry("staged", MemoryType.PROJECT, created=date(2026, 1, 1), state=MemoryState.PENDING),
        _entry("demoted", MemoryType.PROJECT, created=date(2026, 1, 1), state=MemoryState.ARCHIVED),
    ]

    assert hygiene_candidates(entries, now=_NOW, is_alive=_all_dead) == []
