"""경계 템플릿 + init 온보딩(제안 형태) 검증."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pouch.boundary.templates import BOUNDARY_TEMPLATES, to_memory
from pouch.memory.model import SOURCE_USER, MemoryScope, MemoryType
from pouch.memory.store import MemoryStore


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    return tmp_path


# ── 템플릿(순수) ─────────────────────────────────────────────────────────


def test_templates_are_safety_boundaries() -> None:
    assert len(BOUNDARY_TEMPLATES) >= 1
    for t in BOUNDARY_TEMPLATES:
        mem = to_memory(t, now=date(2026, 7, 15))
        assert mem.type is MemoryType.BOUNDARY
        assert mem.direction is not None  # 방향 필수
        assert mem.scope is MemoryScope.GLOBAL  # 안전 경계는 전역
        assert mem.source == SOURCE_USER  # 사람이 고른 것


# ── 온보딩(제안) ─────────────────────────────────────────────────────────


def test_onboarding_skipped_on_yes(workspace: Path) -> None:
    # --yes(비대화형)에선 경계를 강요하지 않는다(선호는 감지된 사실이 아니다).
    from pouch.init.commands import _maybe_offer_boundaries

    _maybe_offer_boundaries(yes=True)
    assert [m for m in MemoryStore().list() if m.type is MemoryType.BOUNDARY] == []


def test_onboarding_saves_only_picked(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import questionary

    from pouch.init.commands import _maybe_offer_boundaries

    picked = BOUNDARY_TEMPLATES[0].name

    class _Ask:
        def ask(self) -> list[str]:
            return [picked]

    monkeypatch.setattr(questionary, "checkbox", lambda *a, **k: _Ask())
    _maybe_offer_boundaries(yes=False)

    boundaries = {m.name for m in MemoryStore().list() if m.type is MemoryType.BOUNDARY}
    assert boundaries == {picked}  # 고른 하나만


def test_onboarding_excludes_already_set(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import questionary

    from pouch.init.commands import _maybe_offer_boundaries

    # 이미 걸린 경계는 후보(체크박스)에서 빠진다.
    MemoryStore().save(to_memory(BOUNDARY_TEMPLATES[0], now=date.today()))
    captured: dict[str, list[str]] = {}

    class _Ask:
        def ask(self) -> list[str]:
            return []

    def _fake_checkbox(_message: str, choices: list) -> _Ask:
        captured["values"] = [c.value for c in choices]
        return _Ask()

    monkeypatch.setattr(questionary, "checkbox", _fake_checkbox)
    _maybe_offer_boundaries(yes=False)

    assert BOUNDARY_TEMPLATES[0].name not in captured["values"]


def test_onboarding_no_candidates_returns_quietly(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import questionary

    from pouch.init.commands import _maybe_offer_boundaries

    # 모든 템플릿이 이미 걸려 있으면 체크박스를 아예 안 띄운다.
    for t in BOUNDARY_TEMPLATES:
        MemoryStore().save(to_memory(t, now=date.today()))

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("후보가 없으면 questionary를 부르면 안 된다")

    monkeypatch.setattr(questionary, "checkbox", _boom)
    _maybe_offer_boundaries(yes=False)  # 예외 없이 조용히 반환
