"""훅 CLI 계약 — 들이는 입구와 "원문 표시 + 동의" 설치.

훅은 내 컴퓨터에서 명령을 실제로 실행하므로, 설치 관문이 다른 종류보다
한 단계 무겁다(배승도 결정, 2026-07-07): 실행될 명령 원문을 반드시 보여주고
동의를 받는다. --yes로 물음은 건너뛰어도 명령 출력은 항상 남는다.

  ① `catalog import <hooks.json>` — 단독 훅 파일도 들일 수 있다
  ② 훅 설치: 명령 원문이 화면에 나오고, 동의해야 배선된다
  ③ 거절하면 배선되지 않는다
  ④ --yes: 물음 없이 배선되지만 명령 원문 출력은 그대로 남는다
  ⑤ 신호 없는 종류(훅)는 evolve의 "안 쓰는 도구" 후보에서 빠진다 —
     훅은 사용 기록에 안 찍힐 뿐 매 사건마다 일하고 있다 (경계를 위생에서
     제외한 것과 같은 이유: 신호 없음 ≠ 안 쓰임)
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pouch import paths
from pouch.cli import app
from pouch.hooks.settings import load_settings

runner = CliRunner()

_HOOKS_JSON = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "node check.js"}],
                "description": "Bash 실행 전 점검",
                "id": "pre:bash:check",
            }
        ]
    }
}


def _import_hooks_file(tmp_path: Path) -> None:
    hooks_file = tmp_path / "hooks.json"
    hooks_file.write_text(json.dumps(_HOOKS_JSON), encoding="utf-8")
    result = runner.invoke(app, ["catalog", "import", str(hooks_file)])
    assert result.exit_code == 0, result.stdout


def _wired_commands(event: str) -> list[str]:
    settings = load_settings(paths.claude_settings_path())
    return [
        h.get("command")
        for group in settings.get("hooks", {}).get(event, [])
        for h in group.get("hooks", [])
    ]


def test_contract1_import_standalone_hooks_json(tmp_path: Path) -> None:
    _import_hooks_file(tmp_path)

    # 관문 (다): import는 소스로 담는다. 훅은 usage 신호가 없어 실사용 진입 경로가
    # 없으므로(정정 3) 소스에 남아 --sources·명시 install로만 보인다(올바른 경계).
    result = runner.invoke(app, ["catalog", "list", "--sources"])
    assert "pre-bash-check" in result.stdout


def test_contract2_install_shows_command_and_asks(tmp_path: Path) -> None:
    _import_hooks_file(tmp_path)

    result = runner.invoke(
        app, ["catalog", "install", "pre-bash-check"], input="y\n"
    )

    assert result.exit_code == 0, result.stdout
    assert "node check.js" in result.stdout  # 실행될 명령 원문 표시
    assert "node check.js" in _wired_commands("PreToolUse")


def test_contract3_decline_leaves_settings_untouched(tmp_path: Path) -> None:
    _import_hooks_file(tmp_path)

    result = runner.invoke(
        app, ["catalog", "install", "pre-bash-check"], input="n\n"
    )

    assert result.exit_code == 0
    assert "node check.js" not in _wired_commands("PreToolUse")


def test_contract4_yes_skips_question_but_prints_command(tmp_path: Path) -> None:
    _import_hooks_file(tmp_path)

    result = runner.invoke(app, ["catalog", "install", "pre-bash-check", "--yes"])

    assert result.exit_code == 0, result.stdout
    assert "node check.js" in result.stdout  # --yes여도 원문 출력은 남는다
    assert "node check.js" in _wired_commands("PreToolUse")


def test_contract5_hooks_excluded_from_drop_candidates(tmp_path: Path) -> None:
    _import_hooks_file(tmp_path)
    runner.invoke(app, ["catalog", "install", "pre-bash-check", "--yes"])

    # 사용 기록이 전혀 없어도(훅은 원래 안 찍힘) 내리자는 제안이 없어야 한다
    result = runner.invoke(app, ["evolve", "--yes"])

    assert result.exit_code == 0
    assert "pre-bash-check" not in result.stdout or "안 쓰는 도구" not in result.stdout


def test_contract6_catalog_uninstall_takes_hook_down(tmp_path: Path) -> None:
    """훅은 evolve 후보에서 빠지므로 손으로 내리는 문이 반드시 있어야 한다."""
    _import_hooks_file(tmp_path)
    runner.invoke(app, ["catalog", "install", "pre-bash-check", "--yes"])
    assert "node check.js" in _wired_commands("PreToolUse")

    result = runner.invoke(app, ["catalog", "uninstall", "pre-bash-check"])

    assert result.exit_code == 0, result.stdout
    assert "node check.js" not in _wired_commands("PreToolUse")
    # 카탈로그엔 남아있다 — 떨어진다 ≠ 삭제된다
    listing = runner.invoke(app, ["catalog", "list"])
    assert "pre-bash-check" in listing.stdout
