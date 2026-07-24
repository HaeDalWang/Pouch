"""세트 ↔ 저장소 참조 — Phase 4.8 조각 ⑤. 몸통을 못 담으면 주소로 가리킨다.

배승도 락(2026-07-24): 세트는 도구 모음이라 여러 저장소를 걸칠 수 있다.
set-export-plugin-mcp-gap("원격 MCP를 세트에 못 담음")을 닫는 길:

  - export: 저장소 출신 도구는 경로 대신 저장소 참조(이름·주소·도구들)로 굳는다
  - apply: 저장소가 등록돼 있어야 설치한다 — 등록은 신뢰 표명이라 세트가 대신
    못 한다(안 물린 저장소는 정직 보고 + 등록 안내, 인질 금지)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pouch.catalog.store import CatalogStore
from pouch.repos.index import index_repo
from pouch.repos.manage import add_repo
from pouch.sets.apply import apply_set
from pouch.sets.export import build_export_set
from pouch.sets.model import RepoRef, SetItem, StarterSet


# --- 모델: 저장소 참조가 세트 파일에 실린다 ---


def test_repo_ref_round_trips_through_json() -> None:
    item = SetItem(repo=RepoRef(name="team", url="git@x:y.git", tools=("a", "b")))

    parsed = SetItem(repo=RepoRef.from_dict(item.to_dict()["repo"]))

    assert parsed == item


def test_install_count_includes_repo_tools() -> None:
    starter = StarterSet(
        name="s", title="s", description="", match_tokens=(),
        items=(SetItem(repo=RepoRef(name="team", url="u", tools=("a", "b"))),),
    )

    assert starter.install_count() == 2


# --- export: 저장소 출신은 주소로 굳는다 ---


def _repo_sourced_entry(entry_id: str, repo: str):
    from pouch.catalog.model import ToolEntry, ToolKind

    return ToolEntry.vendored(
        id=entry_id, kind=ToolKind.SKILL, source=f"repo:{repo}", title=entry_id,
        description="d", upstream=f"/home/u/.pouch/repos/{repo}/skills/{entry_id}/SKILL.md",
        synced_at="s",
    )


def test_export_folds_repo_tools_into_one_repo_ref(tmp_path: Path) -> None:
    """같은 저장소 출신 여러 도구가 참조 하나로 묶인다(세트는 저장소를 걸친다)."""
    entries = [_repo_sourced_entry("a-tool", "team"), _repo_sourced_entry("b-tool", "team")]

    result = build_export_set(
        "my-set", entries, {"a-tool", "b-tool"}, home=tmp_path,
        repo_urls={"team": "git@x:y.git"},
    )

    repo_items = [i for i in result.starter.items if i.repo is not None]
    assert len(repo_items) == 1
    assert repo_items[0].repo.name == "team"
    assert repo_items[0].repo.url == "git@x:y.git"
    assert set(repo_items[0].repo.tools) == {"a-tool", "b-tool"}
    assert result.skipped == ()


def test_export_of_an_unregistered_repo_tool_is_reported(tmp_path: Path) -> None:
    """출신 저장소가 지금 등록돼 있지 않으면 주소를 모른다 — 지어내지 않고 보고."""
    entries = [_repo_sourced_entry("a-tool", "gone")]

    result = build_export_set(
        "my-set", entries, {"a-tool"}, home=tmp_path, repo_urls={},
    )

    assert result.starter.items == ()
    assert any("gone" in reason for reason in result.skipped)


# --- apply: 등록이 먼저다 (인질 금지) ---


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _make_origin(root: Path) -> Path:
    root.mkdir(parents=True)
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "T"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        _run(args, root)
    d = root / "skills" / "deploy-helper"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: deploy-helper\ndescription: deploy tool\n---\n\n# 본문\n",
        encoding="utf-8",
    )
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "init"], root)
    return root


@pytest.fixture()
def surfaces(tmp_path: Path) -> dict:
    return {
        "skills_dir": tmp_path / "surface" / "skills",
        "mcp_config_path": tmp_path / "surface" / ".mcp.json",
        "state_path": tmp_path / "state.json",
    }


def _starter_with_repo(url: str) -> StarterSet:
    return StarterSet(
        name="s", title="s", description="", match_tokens=(),
        items=(SetItem(repo=RepoRef(name="team", url=url, tools=("deploy-helper",))),),
    )


def test_apply_with_unregistered_repo_skips_and_names_the_add_command(
    tmp_path: Path, surfaces: dict
) -> None:
    """세트가 저장소를 대신 등록하지 않는다 — 등록은 신뢰 표명, 사람 몫."""
    report = apply_set(
        _starter_with_repo("git@x:y.git"),
        CatalogStore(catalog_dir=tmp_path / "catalog"),
        synced_at="s",
        repos_dir=tmp_path / "repos", repo_index_root=tmp_path / "repo-index",
        **surfaces,
    )

    assert report.installed == ()
    assert any("pouch repo add team" in reason for reason in report.skipped)


def test_apply_installs_from_a_registered_repo(tmp_path: Path, surfaces: dict) -> None:
    origin = _make_origin(tmp_path / "origin")
    repos_dir = tmp_path / "repos"
    index_root = tmp_path / "repo-index"
    info = add_repo("team", str(origin), repos_dir=repos_dir)
    index_repo("team", info.path, index_dir=index_root / "team", synced_at="s")

    report = apply_set(
        _starter_with_repo(str(origin)),
        CatalogStore(catalog_dir=tmp_path / "catalog"),
        synced_at="s",
        repos_dir=repos_dir, repo_index_root=index_root,
        **surfaces,
    )

    assert "deploy-helper" in report.installed
    assert (surfaces["skills_dir"] / "deploy-helper" / "SKILL.md").exists()


def test_apply_with_a_different_registered_url_is_refused(
    tmp_path: Path, surfaces: dict
) -> None:
    """같은 이름이 딴 주소로 등록돼 있으면 조용히 그걸로 설치하지 않는다."""
    origin = _make_origin(tmp_path / "origin")
    repos_dir = tmp_path / "repos"
    index_root = tmp_path / "repo-index"
    info = add_repo("team", str(origin), repos_dir=repos_dir)
    index_repo("team", info.path, index_dir=index_root / "team", synced_at="s")

    report = apply_set(
        _starter_with_repo("git@somewhere-else:z.git"),
        CatalogStore(catalog_dir=tmp_path / "catalog"),
        synced_at="s",
        repos_dir=repos_dir, repo_index_root=index_root,
        **surfaces,
    )

    assert report.installed == ()
    assert any("다른 주소" in reason for reason in report.skipped)


def test_apply_reports_a_tool_missing_from_the_index(
    tmp_path: Path, surfaces: dict
) -> None:
    origin = _make_origin(tmp_path / "origin")
    repos_dir = tmp_path / "repos"
    index_root = tmp_path / "repo-index"
    info = add_repo("team", str(origin), repos_dir=repos_dir)
    index_repo("team", info.path, index_dir=index_root / "team", synced_at="s")
    starter = StarterSet(
        name="s", title="s", description="", match_tokens=(),
        items=(SetItem(repo=RepoRef(name="team", url=str(origin), tools=("ghost",))),),
    )

    report = apply_set(
        starter,
        CatalogStore(catalog_dir=tmp_path / "catalog"),
        synced_at="s",
        repos_dir=repos_dir, repo_index_root=index_root,
        **surfaces,
    )

    assert report.installed == ()
    assert any("ghost" in reason for reason in report.skipped)
