"""owned 임베드 — 직접 만든 도구의 본문을 세트 파일 안에 통째로 싣는다.

방식 락(배승도, 2026-07-18): 인라인 — 세트 JSON 한 파일이 자기완결.
"남의 도구는 주소, 내 도구는 실물"이 한 파일에 같이 들어간다.

  ① SetItem이 embed(본문 통째)를 담고 JSON 왕복이 된다
  ② export: 표면의 owned를 건너뛰지 않고 embed로 싣는다 (빈 본문은 건너뜀+이유)
  ③ apply: embed를 owned로 되살려 카탈로그에 담고 표면에 올린다
  ④ 이미 있는 owned는 덮지 않는다 (직접 깎은 본문 보호 — importer와 같은 정신)
  ⑤ 남이 준 세트의 embed id가 경로 탈출(`../`)이면 거부한다 (받는 문 안전)
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch.catalog.model import Ownership, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.sets.apply import apply_set
from pouch.sets.export import build_export_set
from pouch.sets.model import EmbeddedTool, SetItem, StarterSet, load_set_file


def _owned(entry_id: str = "my-skill", body: str = "# 내 노하우\n순서대로 한다.") -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id, kind=ToolKind.SKILL, source="local", title=entry_id,
        description="k8s 무중단 업그레이드 노하우", body=body, tags=("devops",),
    )


def _apply(starter: StarterSet, store: CatalogStore, tmp_path: Path):
    return apply_set(
        starter, store,
        skills_dir=tmp_path / "surface",
        mcp_config_path=tmp_path / ".mcp.json",
        settings_path=tmp_path / "settings.json",
        state_path=tmp_path / "state.json",
        synced_at="2026-07-18T00:00:00",
    )


# ── ① 형식: embed 항목의 JSON 왕복 ──────────────────────────────────────


def test_set_item_embed_round_trips_through_json() -> None:
    embed = EmbeddedTool(
        id="my-skill", kind="skill", title="내 스킬",
        description="설명", tags=("devops",), body="# 본문",
    )
    starter = StarterSet(
        name="s", title="s", description="", match_tokens=(),
        items=(SetItem(embed=embed),),
    )

    reloaded = StarterSet.from_dict(json.loads(json.dumps(starter.to_dict())))

    assert reloaded.items[0].embed == embed
    assert reloaded.items[0].source == ""


def test_embed_item_without_body_is_rejected_at_load(tmp_path: Path) -> None:
    # 본문 없는 embed는 형식 위반 — 읽는 문에서 예외(호출부가 격리 처리).
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"name": "s", "items": [{"embed": {"id": "x"}}]}), encoding="utf-8"
    )
    try:
        load_set_file(path)
    except KeyError:
        return
    raise AssertionError("본문 없는 embed가 통과했다")


# ── ② export: owned를 embed로 싣는다 ────────────────────────────────────


def test_export_embeds_owned_body_inline() -> None:
    entry = _owned()

    result = build_export_set("set", [entry], {"my-skill"}, home=Path("/h"))

    assert result.skipped == ()
    item = result.starter.items[0]
    assert item.embed is not None
    assert item.embed.id == "my-skill"
    assert item.embed.body == entry.body
    assert item.embed.description == entry.description


def test_export_skips_owned_with_empty_body_with_reason() -> None:
    entry = _owned(body="   ")

    result = build_export_set("set", [entry], {"my-skill"}, home=Path("/h"))

    assert result.starter.items == ()
    assert any("본문이 비어" in reason for reason in result.skipped)


def test_export_match_tokens_include_embedded_tools() -> None:
    result = build_export_set("set", [_owned()], {"my-skill"}, home=Path("/h"))
    assert "k8s" in result.starter.match_tokens


# ── ③④⑤ apply: 되살리기 + 보호 + 받는 문 안전 ──────────────────────────


def test_apply_restores_embedded_owned_to_catalog_and_surface(tmp_path: Path) -> None:
    result = build_export_set("set", [_owned()], {"my-skill"}, home=Path("/h"))
    store = CatalogStore(catalog_dir=tmp_path / "catalog")

    report = _apply(result.starter, store, tmp_path)

    assert "my-skill" in report.installed
    restored = store.get("my-skill")
    assert restored is not None
    assert restored.ownership is Ownership.OWNED
    assert restored.body == "# 내 노하우\n순서대로 한다."
    assert (tmp_path / "surface" / "my-skill" / "SKILL.md").exists()


def test_apply_does_not_overwrite_existing_owned(tmp_path: Path) -> None:
    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    store.save(_owned(body="# 내가 깎은 버전"))
    incoming = build_export_set("set", [_owned(body="# 남의 버전")], {"my-skill"}, home=Path("/h"))

    report = _apply(incoming.starter, store, tmp_path)

    assert store.get("my-skill").body == "# 내가 깎은 버전"  # 보호됨
    assert any("덮지 않" in reason for reason in report.skipped)


def test_apply_rejects_path_escaping_embed_id(tmp_path: Path) -> None:
    starter = StarterSet(
        name="evil", title="evil", description="", match_tokens=(),
        items=(SetItem(embed=EmbeddedTool(id="../evil", body="# x")),),
    )
    store = CatalogStore(catalog_dir=tmp_path / "catalog")

    report = _apply(starter, store, tmp_path)

    assert report.installed == ()
    assert any("../evil" in reason for reason in report.skipped)
    assert not (tmp_path / "evil.md").exists()  # 카탈로그 폴더 밖에 안 썼다
    assert not (tmp_path / "surface" / ".." / "evil").resolve().exists()


def test_apply_rejects_non_skill_embed_kind_for_now(tmp_path: Path) -> None:
    # v0는 스킬만 — 다른 종류는 건너뛰고 이유를 보고한다(인질 금지).
    starter = StarterSet(
        name="s", title="s", description="", match_tokens=(),
        items=(SetItem(embed=EmbeddedTool(id="h", kind="hook", body="# x")),),
    )
    store = CatalogStore(catalog_dir=tmp_path / "catalog")

    report = _apply(starter, store, tmp_path)

    assert report.installed == ()
    assert any("스킬만" in reason for reason in report.skipped)


# ── 왕복: 참조(vendored)와 embed(owned)가 한 세트에 공존 ─────────────────


def test_mixed_set_round_trips(tmp_path: Path) -> None:
    vendored_md = tmp_path / "src" / "SKILL.md"
    vendored_md.parent.mkdir(parents=True)
    vendored_md.write_text(
        "---\nname: their-skill\ndescription: d\n---\nbody", encoding="utf-8"
    )
    vendored = ToolEntry.vendored(
        id="their-skill", kind=ToolKind.SKILL, source="t", title="t",
        description="d", upstream=str(vendored_md),
    )

    result = build_export_set(
        "mix", [vendored, _owned()], {"their-skill", "my-skill"}, home=Path("/no-home"),
    )
    assert result.skipped == ()

    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    report = _apply(result.starter, store, tmp_path)

    assert set(report.installed) == {"their-skill", "my-skill"}
    assert store.get("my-skill").ownership is Ownership.OWNED
