"""`pouch evolve` 서브커맨드 — 닳고 붙고 떨어진다.

두 입구:
  evolve log : PostToolUse hook이 stdin으로 넘긴 페이로드를 usage.jsonl에 적재.
               best-effort — 무슨 일이 있어도 exit 0(hook이 작업을 막지 않는다).
  evolve     : drop(안 쓰는 것 내리기) + attach(다시 쓰는 것 올리기/편입 안내)를
               제안하고, 동의를 받아야만 움직인다(제안만/자동 아님).

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
from pouch.evolution.attach import AttachCandidate
from pouch.evolution.candidates import DropCandidate, EvolveConfig
from pouch.evolution.compaction import DEFAULT_COMPACT_AFTER_DAYS
from pouch.evolution.orchestrate import (
    apply_drop,
    apply_reattach,
    plan_attach,
    plan_evolution,
    run_compaction,
)
from pouch.evolution.tracker import record_usage
from pouch.memory.evolve import plan_memory_hygiene, plan_memory_pending
from pouch.memory.hygiene import HygieneCandidate
from pouch.memory.model import MemoryEntry
from pouch.memory.store import MemoryStore

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
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 없이 제안을 적용."),
    skills_dir: Path = typer.Option(
        None, "--skills-dir", help="스킬 설치 위치(기본: Claude skills)."
    ),
    mcp_config: Path = typer.Option(
        None, "--mcp-config", help=".mcp.json 위치(기본: 현재 프로젝트)."
    ),
) -> None:
    """안 쓰는 건 내리고, 다시 쓰는 건 올리자고 제안한다(제안만, 자동 없음)."""
    if ctx.invoked_subcommand is not None:
        return  # `evolve log` 등 서브커맨드는 그쪽이 처리한다.

    now = _now()
    store = CatalogStore()
    target_skills = skills_dir or paths.claude_skills_dir()
    target_mcp = mcp_config or paths.project_mcp_config_path()

    # 위생 먼저: 오래된 사용 기록을 요약으로 접는다(무손실). 이후 계획이 접힌
    # 요약을 반영한 정확한 통계 위에서 돈다.
    folded = run_compaction(now=now, after_days=DEFAULT_COMPACT_AFTER_DAYS)
    if folded:
        console.print(f"🧾 오래된 사용 기록 {folded}줄을 요약으로 접었어요(습관은 보존).\n")

    memory_store = MemoryStore()
    drops = plan_evolution(now=now, config=EvolveConfig())
    attaches = plan_attach(now=now, store=store)
    pending = plan_memory_pending(memory_store)
    hygiene = plan_memory_hygiene(memory_store, now=datetime.now().date())
    if not drops and not attaches and not pending and not hygiene:
        console.print("🌊 오르내릴 것이 없습니다. 주머니가 손에 맞게 유지되고 있어요.")
        return

    if drops:
        _propose_drops(
            drops, yes=yes, store=store,
            skills_dir=target_skills, mcp_config_path=target_mcp,
        )
    if attaches:
        _propose_attaches(
            attaches, yes=yes, store=store,
            skills_dir=target_skills, mcp_config_path=target_mcp,
        )
    if pending:
        _propose_memory_pending(pending, yes=yes, store=memory_store)
    if hygiene:
        _propose_memory_hygiene(hygiene, yes=yes, store=memory_store)


def _propose_drops(
    candidates: list[DropCandidate],
    *,
    yes: bool,
    store: CatalogStore,
    skills_dir: Path,
    mcp_config_path: Path,
) -> None:
    """drop 후보를 보여주고, 동의 시 표면에서 내린다."""
    console.print("🌊 [bold]안 쓰는 도구[/bold] (표면에서 내려도 카탈로그·개인화는 남습니다)\n")
    for cand in candidates:
        label = _REASON_LABEL.get(cand.reason, cand.reason)
        console.print(f"  • [cyan]{cand.entry_id}[/cyan] — {label}")

    if not yes and not typer.confirm("\n이 도구들을 표면에서 내릴까요?", default=False):
        console.print("그대로 두었습니다. 언제든 다시 [cyan]pouch evolve[/cyan] 하세요.")
        return

    dropped = [
        cand.entry_id
        for cand in candidates
        if apply_drop(
            cand.entry_id, store=store,
            skills_dir=skills_dir, mcp_config_path=mcp_config_path,
        )
    ]
    console.print(f"\n[green]✓[/green] {len(dropped)}개 내렸습니다: {', '.join(dropped)}")
    console.print("   다시 쓰고 싶으면 재설치 한 번이면 됩니다(개인화는 그대로 살아있어요).")


def _propose_attaches(
    candidates: list[AttachCandidate],
    *,
    yes: bool,
    store: CatalogStore,
    skills_dir: Path,
    mcp_config_path: Path,
) -> None:
    """당겨올 후보를 보여준다 — reattach는 동의 시 실행, adopt·observe는 안내만."""
    reattaches = [c for c in candidates if c.kind == "reattach"]
    adopts = [c for c in candidates if c.kind == "adopt"]
    observes = [c for c in candidates if c.kind == "observe"]

    console.print("\n🧲 [bold]주머니로 당겨올 것[/bold]\n")
    for cand in reattaches:
        console.print(
            f"  • [cyan]{cand.entry_id}[/cyan] — 표면에 없는데 최근 {cand.count}회 씀"
        )
    for cand in adopts:
        console.print(
            f"  • [cyan]{cand.entry_id}[/cyan] — 주머니 밖인데 최근 {cand.count}회 씀"
            f" → [cyan]pouch catalog import[/cyan]로 편입"
        )
    for cand in observes:
        console.print(
            f"  • [cyan]{cand.entry_id}[/cyan] — 플러그인이 관리 중, 최근 {cand.count}회 씀"
            " [dim](관측만)[/dim]"
        )

    if not reattaches:
        return
    if not yes and not typer.confirm("\n표면에 다시 올릴까요?", default=False):
        console.print("그대로 두었습니다.")
        return

    restored: list[str] = []
    for cand in reattaches:
        try:
            if apply_reattach(
                cand.entry_id, store=store,
                skills_dir=skills_dir, mcp_config_path=mcp_config_path,
            ):
                restored.append(cand.entry_id)
        except (ValueError, FileNotFoundError) as exc:
            console.print(f"  [red]✗[/red] {cand.entry_id}: {exc}")
    if restored:
        console.print(f"\n[green]✓[/green] {len(restored)}개 다시 올렸습니다: {', '.join(restored)}")


def _propose_memory_pending(
    entries: list[MemoryEntry], *, yes: bool, store: MemoryStore
) -> None:
    """들어오는 문 — 저마찰로 스테이징된 기억을 확인하고 인덱스에 올린다."""
    console.print("\n🆕 [bold]확인할 기억[/bold] (저마찰로 스테이징됨)\n")
    for entry in entries:
        console.print(f"  • [cyan]{entry.name}[/cyan] ({entry.type.value}) — {entry.description}")

    if not yes and not typer.confirm("\n확인하고 인덱스에 올릴까요?", default=False):
        console.print("그대로 두었습니다. pending으로 남아있어요.")
        return

    for entry in entries:
        store.promote(entry)
    console.print(f"\n[green]✓[/green] {len(entries)}개 확인했습니다: {', '.join(e.name for e in entries)}")


def _propose_memory_hygiene(
    candidates: list[HygieneCandidate], *, yes: bool, store: MemoryStore
) -> None:
    """나가는 문 — 낡거나 죽은 기억을 인덱스에서 강등 제안한다(파일은 남음)."""
    console.print("\n🧹 [bold]정리할 기억[/bold] (인덱스에서 내려도 파일은 남습니다)\n")
    for cand in candidates:
        console.print(f"  • [cyan]{cand.name}[/cyan] ({cand.type.value}) — {cand.detail}")

    if not yes and not typer.confirm("\n인덱스에서 내릴까요?", default=False):
        console.print("그대로 두었습니다. 다시 쓰고 싶으면 recall로 찾을 수 있어요.")
        return

    demoted: list[str] = []
    for cand in candidates:
        entry = store.get(cand.name, cand.scope)
        if entry is not None:
            store.demote(entry)
            demoted.append(cand.name)
    console.print(f"\n[green]✓[/green] {len(demoted)}개 내렸습니다: {', '.join(demoted)}")
    console.print("   다시 필요하면 [cyan]pouch memory recall[/cyan]로 찾을 수 있어요(파일은 그대로).")
