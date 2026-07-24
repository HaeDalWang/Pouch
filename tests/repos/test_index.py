"""저장소 색인 — Phase 4.8 조각 ②. sweep의 원격판.

등록한 저장소(클론)를 하나의 도구통으로 보고 훑어, 도구 목록을 저장소별 색인
티어(`~/.pouch/repo-index/<이름>/`)에 재운다. 핵심 계약:

  - 아는 배치만(skills/·agents/·commands/·rules/·.mcp.json) — 모르는 구조는
    조용히 안 잡히고, 깨진 조각은 이유와 함께 건너뛴다(인질 금지)
  - 색인은 가리키기만 — 카탈로그·표면을 안 건드린다
  - 색인은 파생물 — 재색인은 지우고 다시 만든다(클론이 유일한 진실이라
    upstream에서 사라진 도구가 색인에 유령으로 안 남는다)
"""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.store import CatalogStore
from pouch.repos.index import index_repo


def _make_clone(root: Path) -> Path:
    """아는 배치를 갖춘 가짜 클론 — git일 필요는 없다(색인은 파일만 본다)."""
    (root / "skills" / "deploy-helper").mkdir(parents=True)
    (root / "skills" / "deploy-helper" / "SKILL.md").write_text(
        "---\nname: deploy-helper\ndescription: deploy tool\n---\n\n# 본문\n",
        encoding="utf-8",
    )
    (root / "agents").mkdir()
    (root / "agents" / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: review agent\n---\n\n# 본문\n",
        encoding="utf-8",
    )
    (root / "commands").mkdir()
    (root / "commands" / "ship.md").write_text("# ship\n", encoding="utf-8")
    (root / ".mcp.json").write_text(
        '{"mcpServers": {"team-mcp": {"command": "uvx", "args": ["x"]}}}\n',
        encoding="utf-8",
    )
    return root


def test_known_layouts_are_indexed(tmp_path: Path) -> None:
    clone = _make_clone(tmp_path / "clone")
    index_dir = tmp_path / "index"

    report = index_repo("team", clone, index_dir=index_dir, synced_at="2026-07-24")

    ids = {e.id for e in CatalogStore(catalog_dir=index_dir).list()}
    assert {"deploy-helper", "reviewer", "ship", "team-mcp"} <= ids
    assert len(report.staged) >= 4


def test_unknown_structure_is_quietly_not_found(tmp_path: Path) -> None:
    """아는 배치가 없으면 색인이 비고, 죽지 않는다 — 못 찾음은 흠이 아니다."""
    clone = tmp_path / "clone"
    (clone / "random" / "stuff").mkdir(parents=True)
    (clone / "random" / "stuff" / "note.md").write_text("메모\n", encoding="utf-8")

    report = index_repo("team", clone, index_dir=tmp_path / "index", synced_at="s")

    assert report.staged == ()
    assert list(CatalogStore(catalog_dir=tmp_path / "index").list()) == []


def test_a_broken_piece_does_not_hold_the_rest_hostage(tmp_path: Path) -> None:
    """이름 없는 스킬은 이유와 함께 건너뛰고, 성한 것은 담는다."""
    clone = _make_clone(tmp_path / "clone")
    (clone / "skills" / "broken").mkdir()
    (clone / "skills" / "broken" / "SKILL.md").write_text("이름 없음\n", encoding="utf-8")

    report = index_repo("team", clone, index_dir=tmp_path / "index", synced_at="s")

    assert report.skipped  # 건너뛴 이유가 보고된다
    ids = {e.id for e in CatalogStore(catalog_dir=tmp_path / "index").list()}
    assert "deploy-helper" in ids  # 성한 것은 살았다


def test_reindex_drops_tools_that_upstream_removed(tmp_path: Path) -> None:
    """색인은 파생물 — 클론에서 사라진 도구가 색인에 유령으로 안 남는다."""
    clone = _make_clone(tmp_path / "clone")
    index_dir = tmp_path / "index"
    index_repo("team", clone, index_dir=index_dir, synced_at="s")

    (clone / "commands" / "ship.md").unlink()
    index_repo("team", clone, index_dir=index_dir, synced_at="s")

    ids = {e.id for e in CatalogStore(catalog_dir=index_dir).list()}
    assert "ship" not in ids
    assert "deploy-helper" in ids


def test_indexing_touches_neither_catalog_nor_sources(tmp_path: Path, monkeypatch) -> None:
    """색인은 가리키기만 — 장부(카탈로그)·로컬 대기실(sources)이 그대로다."""
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "home"))
    from pouch import paths

    clone = _make_clone(tmp_path / "clone")
    index_repo("team", clone, index_dir=tmp_path / "index", synced_at="s")

    assert list(CatalogStore().list()) == []
    assert list(CatalogStore(catalog_dir=paths.sources_dir()).list()) == []
