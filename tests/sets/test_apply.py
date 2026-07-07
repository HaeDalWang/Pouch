"""세트 적용 계약 — 출처에서 가져와 채우고, 고른 것만 표면에 올린다.

  ① 항목의 source를 가져와(import) 카탈로그를 채우고, install 목록만 표면에 올린다
  ② source가 없으면(경로 증발) 그 항목만 건너뛰고 이유를 보고한다 — 인질 금지
  ③ install id가 카탈로그에 없으면 그것만 건너뛰고 이유를 보고한다
  ④ install이 빈 항목은 담기만 한다 (표면에 안 올림)
  ⑤ 플러그인 중첩 구조(<플러그인>/<버전>/)도 안쪽을 찾아 들어간다 (기존 발견 로직 재사용)
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch.catalog.store import CatalogStore
from pouch.evolution.state import active_entries
from pouch.sets.apply import apply_set
from pouch.sets.model import SetItem, StarterSet


def _fake_plugin(root: Path, skills: list[str]) -> Path:
    """스킬 몇 개짜리 가짜 플러그인 디렉토리를 만든다."""
    for skill in skills:
        skill_dir = root / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill}\ndescription: d\n---\nbody", encoding="utf-8"
        )
    return root


def _set(items: list[SetItem]) -> StarterSet:
    return StarterSet(
        name="demo", title="데모", description="", match_tokens=("aws",),
        items=tuple(items),
    )


def _apply(starter, tmp_path, store):
    return apply_set(
        starter, store,
        skills_dir=tmp_path / "surface",
        mcp_config_path=tmp_path / ".mcp.json",
        settings_path=tmp_path / "settings.json",
        state_path=tmp_path / "state.json",
        synced_at="2026-07-07T00:00:00",
    )


def test_contract1_imports_source_and_installs_selected(tmp_path: Path) -> None:
    plugin = _fake_plugin(tmp_path / "plugin", ["aws-iam", "aws-cdk", "aws-sdk-swift-usage"])
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    starter = _set([SetItem(source=str(plugin), install=("aws-iam", "aws-cdk"))])

    report = _apply(starter, tmp_path, store)

    # 카탈로그엔 3개 다 담기고(창고), 표면엔 고른 2개만 올라간다(연장통)
    assert report.imported == 3
    assert set(report.installed) == {"aws-iam", "aws-cdk"}
    assert (tmp_path / "surface" / "aws-iam" / "SKILL.md").exists()
    assert not (tmp_path / "surface" / "aws-sdk-swift-usage").exists()
    assert "aws-iam" in active_entries(state_path=tmp_path / "state.json")


def test_contract2_missing_source_skipped_with_reason(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    starter = _set([SetItem(source=str(tmp_path / "nowhere"), install=("x",))])

    report = _apply(starter, tmp_path, store)

    assert report.imported == 0
    assert report.installed == ()
    assert len(report.skipped) == 1
    assert "nowhere" in report.skipped[0]


def test_contract3_missing_install_id_skipped_with_reason(tmp_path: Path) -> None:
    plugin = _fake_plugin(tmp_path / "plugin", ["aws-iam"])
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    starter = _set([SetItem(source=str(plugin), install=("aws-iam", "ghost-skill"))])

    report = _apply(starter, tmp_path, store)

    assert set(report.installed) == {"aws-iam"}
    assert any("ghost-skill" in reason for reason in report.skipped)


def test_contract4_empty_install_imports_only(tmp_path: Path) -> None:
    plugin = _fake_plugin(tmp_path / "plugin", ["aws-iam"])
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    starter = _set([SetItem(source=str(plugin))])

    report = _apply(starter, tmp_path, store)

    assert report.imported == 1
    assert report.installed == ()
    assert not (tmp_path / "surface").exists()


def test_contract5_nested_plugin_root_discovered(tmp_path: Path) -> None:
    # marketplace 캐시 구조: <플러그인>/<버전>/skills/…
    nested = tmp_path / "cache" / "aws-core" / "1.0.0"
    _fake_plugin(nested, ["aws-iam"])
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    starter = _set([SetItem(source=str(tmp_path / "cache"), install=("aws-iam",))])

    report = _apply(starter, tmp_path, store)

    assert report.installed == ("aws-iam",)
