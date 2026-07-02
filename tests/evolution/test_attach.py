"""attach 후보 계약 — Phase 4.6 ③: 진화의 빠진 반쪽("붙는다").

  ① 카탈로그에 있고 + 표면에 없고 + 최근 썼다 → reattach 후보
  ② 표면에 이미 있으면 후보 아님
  ③ 카탈로그 밖인데 최근 자주 썼다(임계 이상) → adopt 후보
  ④ 카탈로그 밖 + 드물게 씀(임계 미만) → 노이즈로 컷
  ⑤ 최근 창 밖의 옛 사용은 신호가 아니다 — stale-drop 직후 즉시 재부착으로
     되돌아오는 진동(oscillation)을 창(7일) < stale 임계(30일)로 구조 차단
  ⑥ 정렬: reattach 먼저, 그다음 adopt, 각각 횟수 내림차순
  ⑦ CLI: drop된 도구를 다시 쓰면 evolve가 재부착을 제안하고 --yes로 복귀,
     overlay(개인화)는 전 과정 생존 (가역성 왕복 완결)
  ⑧ CLI: 카탈로그 밖 다빈도 도구는 편입 안내가 뜬다 (제안만, 자동 없음)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from pouch.cli import app
from pouch.evolution.attach import AttachCandidate, attach_candidates
from pouch.evolution.usage_log import UsageEvent

runner = CliRunner()

_NOW = "2026-07-02T12:00:00"


def _event(entry_id: str, ts: str = "2026-07-01T09:00:00") -> UsageEvent:
    return UsageEvent(entry_id=entry_id, ts=ts)


def test_contract1_cataloged_inactive_used_is_reattach() -> None:
    candidates = attach_candidates(
        [_event("aws-iam")], catalog_ids={"aws-iam"}, active_ids=set(), now=_NOW
    )

    assert candidates == [
        AttachCandidate(entry_id="aws-iam", kind="reattach", count=1,
                        last_used="2026-07-01T09:00:00")
    ]


def test_contract2_active_entry_is_not_candidate() -> None:
    candidates = attach_candidates(
        [_event("aws-iam")], catalog_ids={"aws-iam"}, active_ids={"aws-iam"}, now=_NOW
    )

    assert candidates == []


def test_contract3_uncataloged_frequent_is_adopt() -> None:
    events = [_event("exa") for _ in range(3)]

    candidates = attach_candidates(events, catalog_ids=set(), active_ids=set(), now=_NOW)

    assert len(candidates) == 1
    assert candidates[0].kind == "adopt" and candidates[0].count == 3


def test_contract4_uncataloged_rare_is_noise() -> None:
    events = [_event("once-off"), _event("once-off")]  # 임계(3) 미만

    candidates = attach_candidates(events, catalog_ids=set(), active_ids=set(), now=_NOW)

    assert candidates == []


def test_contract5_old_usage_is_not_a_signal() -> None:
    # stale(30일)로 떨어진 도구의 옛 기록 — 창(7일) 밖이라 재부착 신호가 아니다
    old = _event("stale-tool", ts="2026-05-01T09:00:00")

    candidates = attach_candidates(
        [old], catalog_ids={"stale-tool"}, active_ids=set(), now=_NOW
    )

    assert candidates == []


def test_contract6_reattach_before_adopt_count_desc() -> None:
    events = [
        _event("adopt-me"), _event("adopt-me"), _event("adopt-me"),
        _event("adopt-me"), _event("adopt-me"),
        _event("bring-back"),
    ]

    candidates = attach_candidates(
        events, catalog_ids={"bring-back"}, active_ids=set(), now=_NOW
    )

    assert [c.kind for c in candidates] == ["reattach", "adopt"]
    assert candidates[0].entry_id == "bring-back"  # 횟수 적어도 reattach 우선


def _fresh_ts(hours_ago: int = 1) -> str:
    return (datetime.now() - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def test_contract7_cli_roundtrip_drop_use_reattach_overlay_survives(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))

    from pouch.catalog.install import install_entry
    from pouch.catalog.model import Overlay, ToolEntry, ToolKind
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.orchestrate import apply_drop
    from pouch.evolution.state import active_entries
    from pouch.evolution.usage_log import append_event

    upstream = tmp_path / "up" / "aws-iam" / "SKILL.md"
    upstream.parent.mkdir(parents=True)
    upstream.write_text("---\nname: aws-iam\ndescription: d\n---\n\n본문", encoding="utf-8")
    entry = ToolEntry.vendored(
        id="aws-iam", kind=ToolKind.SKILL, source="aws", title="aws-iam",
        description="d", upstream=str(upstream), synced_at="2026-01-01",
        overlay=Overlay(boundaries=("prod-gate",)),
    )
    store = CatalogStore()
    store.save(entry)
    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"
    install_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config)

    # 떨어뜨린다 → 표면에서 사라짐
    apply_drop("aws-iam", store=store, skills_dir=skills_dir, mcp_config_path=mcp_config)
    assert not (skills_dir / "aws-iam" / "SKILL.md").exists()

    # 그런데 최근에 다시 썼다
    append_event(UsageEvent(entry_id="aws-iam", ts=_fresh_ts()))

    result = runner.invoke(
        app,
        ["evolve", "--yes", "--skills-dir", str(skills_dir), "--mcp-config", str(mcp_config)],
    )

    assert result.exit_code == 0
    assert (skills_dir / "aws-iam" / "SKILL.md").exists()  # 표면 복귀
    assert "aws-iam" in active_entries()  # 상태도 active
    survived = store.get("aws-iam")
    assert survived is not None and survived.overlay.boundaries == ("prod-gate",)


def test_contract8_cli_shows_adopt_hint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POUCH_HOME", str(tmp_path))
    from pouch.evolution.usage_log import append_event

    for _ in range(3):
        append_event(UsageEvent(entry_id="plugin_ecc_exa", ts=_fresh_ts()))

    result = runner.invoke(app, ["evolve", "--yes"])

    assert result.exit_code == 0
    assert "plugin_ecc_exa" in result.output
    assert "catalog import" in result.output  # 편입은 안내만, 자동 없음
