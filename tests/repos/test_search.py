"""저장소 색인 검색 — Phase 4.8 조각 ③의 '빈손 입구' (helm search repo 대응).

빈손 사용자는 '이거 써봐'의 기준(반복 사용)이 없어서 추천이 안 뜬다 — 그런
사람에게 색인을 직접 보는 문이 이 검색이다. 근거는 사용 기록이 아니라
"이 저장소가 담고 있다"는 실재 사실뿐이라 기준 없이도 정직하다.
"""

from __future__ import annotations

from pathlib import Path

from pouch.repos.index import index_repo, indexed_entries, search_index


def _clone_with(root: Path, skills: dict[str, str]) -> Path:
    for name, desc in skills.items():
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {desc}\n---\n\n# 본문\n",
            encoding="utf-8",
        )
    return root


def test_indexed_entries_carry_repo_scoped_identity(tmp_path: Path) -> None:
    """색인 엔트리의 정체는 `<저장소>/<도구>` — 출처가 이름에 실려 다닌다."""
    clone = _clone_with(tmp_path / "clone", {"deploy-helper": "deploy tool"})
    root = tmp_path / "index-root"
    index_repo("team", clone, index_dir=root / "team", synced_at="s")

    entries = indexed_entries(root)

    assert [e.id for e in entries] == ["team/deploy-helper"]


def test_search_matches_by_keyword_across_repos(tmp_path: Path) -> None:
    root = tmp_path / "index-root"
    index_repo(
        "team",
        _clone_with(tmp_path / "c1", {"deploy-helper": "deploy to kubernetes"}),
        index_dir=root / "team", synced_at="s",
    )
    index_repo(
        "public",
        _clone_with(tmp_path / "c2", {"cost-report": "aws cost report"}),
        index_dir=root / "public", synced_at="s",
    )

    hits = search_index(root, "cost")

    assert [e.id for e in hits] == ["public/cost-report"]


def test_search_is_case_insensitive_and_looks_at_descriptions(tmp_path: Path) -> None:
    root = tmp_path / "index-root"
    index_repo(
        "team",
        _clone_with(tmp_path / "c1", {"deploy-helper": "deploy to Kubernetes"}),
        index_dir=root / "team", synced_at="s",
    )

    assert [e.id for e in search_index(root, "KUBER")] == ["team/deploy-helper"]


def test_empty_query_lists_everything(tmp_path: Path) -> None:
    root = tmp_path / "index-root"
    index_repo(
        "team",
        _clone_with(tmp_path / "c1", {"a-tool": "x", "b-tool": "y"}),
        index_dir=root / "team", synced_at="s",
    )

    assert len(search_index(root, "")) == 2


def test_search_with_no_repos_is_just_empty(tmp_path: Path) -> None:
    assert search_index(tmp_path / "nothing", "any") == []
