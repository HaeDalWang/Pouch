"""evolve orchestration 계약 검증 — 조각들을 잇는 얇은 planner.

순수 계획(plan_evolution)과 IO 적용(apply_drop)을 분리한다:
  plan_evolution: usage_log → aggregate → active state → drop 후보 (순수 조립)
  apply_drop    : uninstall_entry(표면만) + mark_dropped(상태). 카탈로그 불변.

  ① plan_evolution: 로그·상태를 읽어 후보를 계산한다
  ② apply_drop: 표면에서 내리고 상태를 dropped로 — 카탈로그 엔트리+overlay 생존
  ③ apply_drop 후 그 entry는 active에서 빠진다 (재계획 시 재추천 안 됨)
"""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.evolution.candidates import EvolveConfig
from pouch.evolution.orchestrate import apply_drop, plan_evolution
from pouch.evolution.state import active_entries, record_installed
from pouch.evolution.usage_log import UsageEvent, append_event

_NOW = "2026-07-01T00:00:00"
_CFG = EvolveConfig(grace_days=14, stale_days=30)


def _vendored_entry(id: str, upstream: Path) -> ToolEntry:
    return ToolEntry.vendored(
        id=id, kind=ToolKind.SKILL, source="aws", title=id, description="d",
        upstream=str(upstream), synced_at="2026-07-01",
        overlay=Overlay(boundaries=("prod-gate",)),
    )


def _make_upstream(tmp_path: Path, id: str) -> Path:
    p = tmp_path / "up" / id / "SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_text(f"---\nname: {id}\ndescription: d\n---\n\n# {id}\n\n본문", encoding="utf-8")
    return p


def test_contract1_plan_computes_candidates_from_logs(tmp_path: Path) -> None:
    usage = tmp_path / "usage.jsonl"
    state = tmp_path / "state.json"
    # 두 도구 모두 30일 전 설치, 하나만 최근 사용
    record_installed("used", now="2026-06-01T00:00:00", state_path=state)
    record_installed("never", now="2026-06-01T00:00:00", state_path=state)
    append_event(UsageEvent("used", "2026-06-29T00:00:00"), log_path=usage)

    cands = plan_evolution(now=_NOW, config=_CFG, usage_path=usage, state_path=state)

    ids = {c.entry_id for c in cands}
    assert "never" in ids  # never-used + 유예 지남
    assert "used" not in ids  # 최근 사용 → immune


def test_contract2_apply_drop_preserves_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    skills = tmp_path / "skills"
    mcp = tmp_path / ".mcp.json"
    state = tmp_path / "state.json"
    store = CatalogStore(catalog_dir=catalog)

    upstream = _make_upstream(tmp_path, "aws-iam")
    entry = _vendored_entry("aws-iam", upstream)
    store.save(entry)
    from pouch.catalog.install import install_entry

    install_entry(entry, skills_dir=skills, mcp_config_path=mcp)
    record_installed("aws-iam", now=_NOW, state_path=state)

    apply_drop("aws-iam", store=store, skills_dir=skills, mcp_config_path=mcp, state_path=state)

    # 표면에서 사라짐
    assert not (skills / "aws-iam" / "SKILL.md").exists()
    # ★ 카탈로그 엔트리 + overlay 생존
    survived = store.get("aws-iam")
    assert survived is not None and survived.overlay.boundaries == ("prod-gate",)


def test_contract3_dropped_entry_leaves_active(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    skills = tmp_path / "skills"
    mcp = tmp_path / ".mcp.json"
    state = tmp_path / "state.json"
    store = CatalogStore(catalog_dir=catalog)

    upstream = _make_upstream(tmp_path, "aws-iam")
    entry = _vendored_entry("aws-iam", upstream)
    store.save(entry)
    from pouch.catalog.install import install_entry

    install_entry(entry, skills_dir=skills, mcp_config_path=mcp)
    record_installed("aws-iam", now=_NOW, state_path=state)

    apply_drop("aws-iam", store=store, skills_dir=skills, mcp_config_path=mcp, state_path=state)

    assert active_entries(state_path=state) == {}
