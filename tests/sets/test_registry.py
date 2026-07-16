"""레지스트리(raft 받는 쪽) — git clone/pull로 남의 세트를 당겨온다.

실제 로컬 git repo를 레지스트리 삼아 왕복 검증한다(네트워크 없이 file 경로 clone).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from pouch import paths
from pouch.cli import app

runner = CliRunner()


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _make_registry(root: Path, entries: dict[tuple[str, str], str]) -> Path:
    """sets/<author>/<name>.json을 담은 git 레지스트리 repo를 만든다."""
    root.mkdir(parents=True)
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "Tester"], root)
    _run(["git", "config", "commit.gpgsign", "false"], root)
    _add_sets(root, entries)
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "init"], root)
    return root


def _add_sets(root: Path, entries: dict[tuple[str, str], str]) -> None:
    for (author, name), source in entries.items():
        path = root / "sets" / author / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "name": name, "title": f"{name} 세트", "description": "공유된 것",
                "match": ["aws"],
                "items": [{"source": source, "install": []}],
            }),
            encoding="utf-8",
        )


def test_pull_clones_and_lists_author_scoped(tmp_path: Path) -> None:
    registry = _make_registry(tmp_path / "reg", {("alice", "aws-devops"): "~/nowhere"})

    result = runner.invoke(app, ["set", "pull", str(registry)])
    assert result.exit_code == 0, result.stdout
    assert "1개를 받았습니다" in result.stdout
    assert (paths.registry_dir() / ".git").exists()  # 클론됨

    # 목록에 작성자 스코프로 잡힌다.
    listed = runner.invoke(app, ["set", "list"])
    assert "alice/aws-devops" in listed.stdout


def test_pull_without_url_needs_registry_first() -> None:
    result = runner.invoke(app, ["set", "pull"])
    assert result.exit_code == 1
    assert "처음엔 URL" in result.stdout


def test_pull_refreshes_and_picks_up_new_sets(tmp_path: Path) -> None:
    registry = _make_registry(tmp_path / "reg", {("alice", "one"): "~/x"})
    assert runner.invoke(app, ["set", "pull", str(registry)]).exit_code == 0

    # 레지스트리에 새 세트가 올라온 뒤 — 인자 없이 재-pull하면 잡힌다.
    _add_sets(registry, {("bob", "two"): "~/y"})
    _run(["git", "add", "-A"], registry)
    _run(["git", "commit", "-q", "-m", "add bob"], registry)

    result = runner.invoke(app, ["set", "pull"])
    assert result.exit_code == 0, result.stdout
    listed = runner.invoke(app, ["set", "list"]).stdout
    assert "alice/one" in listed
    assert "bob/two" in listed


def test_pull_rejects_switching_registry(tmp_path: Path) -> None:
    first = _make_registry(tmp_path / "reg1", {("alice", "one"): "~/x"})
    second = _make_registry(tmp_path / "reg2", {("bob", "two"): "~/y"})
    assert runner.invoke(app, ["set", "pull", str(first)]).exit_code == 0

    # 이미 다른 레지스트리가 있으면 조용히 덮지 않고 거부(안내).
    result = runner.invoke(app, ["set", "pull", str(second)])
    assert result.exit_code == 1
    assert "이미 다른 레지스트리" in result.stdout
