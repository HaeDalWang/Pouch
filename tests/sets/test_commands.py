"""세트 CLI·init 배선 계약 — 세트가 사용자를 만나는 두 입구.

내장 세트는 현재 의도적으로 비어 있다: 지어낸 큐레이션은 "남이 만든 정답
세트"라 철회됐고(배승도 판정, 2026-07-07), 실사용에서 굳힌 세트만 들어온다.

  ① `pouch set list` — 세트가 없으면 없다고 안내한다 (내장은 비어 있음)
  ② `pouch set apply <이름> --yes` — 가져오고 올린 결과를 보고한다
  ③ 적용된 것 중 훅이 있으면 실행 명령 원문을 항상 출력한다 (배승도 결정)
  ④ init: 역할·스택이 세트와 맞으면 세트를 먼저 제안하고, --yes면 적용까지 간다
  ⑤ init: 맞는 세트가 없으면 세트 얘기 없이 기존 흐름 그대로
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch import paths
from pouch.cli import app

runner = CliRunner()


def _fake_plugin(root: Path, skills: list[str]) -> Path:
    for skill in skills:
        skill_dir = root / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill}\ndescription: d\n---\nbody", encoding="utf-8"
        )
    return root


def _user_set(name: str, *, source: str, install: list[str], match: list[str]) -> None:
    sets_dir = paths.sets_dir()
    sets_dir.mkdir(parents=True, exist_ok=True)
    (sets_dir / f"{name}.json").write_text(
        json.dumps({
            "name": name, "title": f"{name} 세트", "description": "테스트",
            "match": match,
            "items": [{"source": source, "install": install}],
        }),
        encoding="utf-8",
    )


@pytest.fixture()
def _no_builtin(monkeypatch, tmp_path_factory):
    """내장 세트를 비워 테스트가 이 컴퓨터의 실물 경로에 안 기대게 한다."""
    monkeypatch.setattr(
        "pouch.sets.model._BUILTIN_DIR", tmp_path_factory.mktemp("no_builtin")
    )


def test_contract1_set_list_without_sets_says_so(_no_builtin) -> None:
    result = runner.invoke(app, ["set", "list"])

    assert result.exit_code == 0
    assert "세트가 없습니다" in result.stdout


def test_contract1b_set_list_shows_user_sets(tmp_path: Path, _no_builtin) -> None:
    plugin = _fake_plugin(tmp_path / "plugin", ["aws-iam"])
    _user_set("mine", source=str(plugin), install=["aws-iam"], match=["aws"])

    result = runner.invoke(app, ["set", "list"])

    assert result.exit_code == 0
    assert "mine" in result.stdout


def test_contract2_set_apply_reports(tmp_path: Path, _no_builtin) -> None:
    plugin = _fake_plugin(tmp_path / "plugin", ["aws-iam", "aws-cdk"])
    _user_set("demo", source=str(plugin), install=["aws-iam"], match=["aws"])

    result = runner.invoke(app, ["set", "apply", "demo", "--yes"])

    assert result.exit_code == 0, result.stdout
    assert "aws-iam" in result.stdout
    assert (paths.claude_skills_dir() / "aws-iam" / "SKILL.md").exists()


def test_contract3_applied_hook_prints_command(tmp_path: Path, _no_builtin) -> None:
    hooks_file = tmp_path / "hooks.json"
    hooks_file.write_text(json.dumps({
        "hooks": {"PreToolUse": [{
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "node check.js"}],
            "id": "pre:bash:check",
        }]}
    }), encoding="utf-8")
    _user_set("hooky", source=str(hooks_file), install=["pre-bash-check"], match=["aws"])

    result = runner.invoke(app, ["set", "apply", "hooky", "--yes"])

    assert result.exit_code == 0, result.stdout
    assert "node check.js" in result.stdout  # 훅 명령 원문은 항상 출력


def test_set_export_freezes_surface_to_file(tmp_path: Path, _no_builtin) -> None:
    # 단독 SKILL.md를 담고(import) 표면에 올린(install) 뒤 세트로 굳힌다.
    skill_md = tmp_path / "src" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\nname: exporttest\ndescription: Terraform on AWS\n---\nbody", encoding="utf-8"
    )
    assert runner.invoke(app, ["catalog", "import", str(skill_md)]).exit_code == 0
    assert runner.invoke(app, ["catalog", "install", "exporttest"]).exit_code == 0

    result = runner.invoke(app, ["set", "export", "frozen", "--yes"])

    assert result.exit_code == 0, result.stdout
    assert "굳혔습니다" in result.stdout
    dest = paths.sets_dir() / "frozen.json"
    assert dest.exists()
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["items"][0]["install"] == ["exporttest"]
    assert "aws" in data["match"]  # 담긴 도구 토큰에서 매칭 파생
    # 곧장 set list에 잡힌다.
    assert "frozen" in runner.invoke(app, ["set", "list"]).stdout


def test_set_export_nothing_on_empty_surface(_no_builtin) -> None:
    result = runner.invoke(app, ["set", "export", "empty"])
    assert result.exit_code == 1
    assert "굳힐 게 없습니다" in result.stdout


def test_contract4_init_offers_matching_set(tmp_path: Path, _no_builtin) -> None:
    plugin = _fake_plugin(tmp_path / "plugin", ["aws-iam"])
    _user_set("demo", source=str(plugin), install=["aws-iam"], match=["aws", "devops"])

    result = runner.invoke(
        app, ["init", "--role", "DevOps", "--stack", "aws", "--yes"]
    )

    assert result.exit_code == 0, result.stdout
    assert "demo 세트" in result.stdout  # 세트를 제안했다
    assert (paths.claude_skills_dir() / "aws-iam" / "SKILL.md").exists()  # 적용까지


def test_contract5_init_without_match_stays_quiet(_no_builtin) -> None:
    result = runner.invoke(
        app, ["init", "--role", "디자인", "--stack", "figma", "--yes"]
    )

    assert result.exit_code == 0, result.stdout
    assert "세트" not in result.stdout  # 맞는 세트가 없으면 조용히 기존 흐름
