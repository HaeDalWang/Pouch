"""`pouch evolve` 서브커맨드 — 닳고 붙고 떨어진다.

두 입구:
  evolve log : PostToolUse hook이 stdin으로 넘긴 페이로드를 usage.jsonl에 적재.
               best-effort — 무슨 일이 있어도 exit 0(hook이 작업을 막지 않는다).
  evolve     : drop 후보를 제안하고, 동의를 받으면 표면에서 내린다(제안만/자동 아님).

"떨어진다 ≠ 삭제된다": drop은 활성 표면에서만 내리고 카탈로그 엔트리+overlay는
생존한다. 시계는 이 경계에서만 읽고(datetime.now), 순수 함수엔 주입한다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from pouch import paths
from pouch.catalog.store import CatalogStore
from pouch.evolution.candidates import EvolveConfig
from pouch.evolution.orchestrate import apply_drop, plan_evolution
from pouch.evolution.tracker import record_usage

app = typer.Typer(
    help="🌊 evolve — 쓸수록 손에 맞게. 안 쓰는 건 정리 제안.",
    no_args_is_help=False,
)
console = Console()

_REASON_LABEL = {
    "never-used": "한 번도 안 씀 (추천이 헛맞았나)",
    "stale": "오래 안 씀 (졸업했나)",
}


def _now() -> str:
    """현재 시각 ISO8601. 시계는 여기서만 읽는다."""
    return datetime.now().isoformat(timespec="seconds")


@app.command("log")
def log() -> None:
    """PostToolUse hook용: stdin 페이로드를 usage.jsonl에 적재(best-effort)."""
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        record_usage(payload, now=_now())
    except Exception:  # noqa: BLE001
        # 추적은 절대 작업을 막지 않는다 — 무슨 일이 있어도 조용히 성공한다.
        pass
    raise typer.Exit(code=0)


@app.callback(invoke_without_command=True)
def evolve(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 없이 후보를 내림."),
    skills_dir: Path = typer.Option(
        None, "--skills-dir", help="스킬 설치 위치(기본: Claude skills)."
    ),
    mcp_config: Path = typer.Option(
        None, "--mcp-config", help=".mcp.json 위치(기본: 현재 프로젝트)."
    ),
) -> None:
    """안 쓰는 도구를 찾아 정리를 제안한다(제안만, 자동 제거 안 함)."""
    if ctx.invoked_subcommand is not None:
        return  # `evolve log` 등 서브커맨드는 그쪽이 처리한다.

    candidates = plan_evolution(now=_now(), config=EvolveConfig())
    if not candidates:
        console.print("🌊 정리할 것이 없습니다. 주머니가 손에 맞게 유지되고 있어요.")
        return

    console.print("🌊 [bold]안 쓰는 도구[/bold] (표면에서 내려도 카탈로그·개인화는 남습니다)\n")
    for cand in candidates:
        label = _REASON_LABEL.get(cand.reason, cand.reason)
        console.print(f"  • [cyan]{cand.entry_id}[/cyan] — {label}")

    if not yes and not typer.confirm("\n이 도구들을 표면에서 내릴까요?", default=False):
        console.print("그대로 두었습니다. 언제든 다시 [cyan]pouch evolve[/cyan] 하세요.")
        return

    store = CatalogStore()
    target_skills = skills_dir or paths.claude_skills_dir()
    target_mcp = mcp_config or paths.project_mcp_config_path()
    dropped = [
        cand.entry_id
        for cand in candidates
        if apply_drop(
            cand.entry_id,
            store=store,
            skills_dir=target_skills,
            mcp_config_path=target_mcp,
        )
    ]
    console.print(f"\n[green]✓[/green] {len(dropped)}개 내렸습니다: {', '.join(dropped)}")
    console.print("   다시 쓰고 싶으면 재설치 한 번이면 됩니다(개인화는 그대로 살아있어요).")
