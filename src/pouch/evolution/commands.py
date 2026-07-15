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
from pouch.catalog.boundary import plan_boundary_drop
from pouch.catalog.model import alias_map
from pouch.catalog.store import CatalogStore
from pouch.evolution.attach import AttachCandidate
from pouch.evolution.candidates import DropCandidate, EvolveConfig, has_usage_signal
from pouch.evolution.core_tools import core_entry_ids
from pouch.evolution.usage_log import read_events
from pouch.evolution.compaction import DEFAULT_COMPACT_AFTER_DAYS
from pouch.evolution.advice import Advice
from pouch.evolution.orchestrate import (
    apply_drop,
    apply_reattach,
    plan_attach,
    plan_evolution,
    plan_plugin_advice,
    reconcile,
    run_compaction,
)
from pouch.evolution.preview import preview_attach, preview_drop
from pouch.evolution.similar import plan_try_this
from pouch.evolution.state import active_entries
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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="목록·이유·되돌림만 보여주고 아무것도 안 함(볼게, 해 아님)."
    ),
    skills_dir: Path = typer.Option(
        None, "--skills-dir", help="스킬 설치 위치(기본: Claude skills)."
    ),
    mcp_config: Path = typer.Option(
        None, "--mcp-config", help=".mcp.json 위치(기본: 현재 프로젝트)."
    ),
) -> None:
    """안 쓰는 건 내리고, 다시 쓰는 건 올리자고 제안한다(제안만, 자동 없음).

    --dry-run은 '정리하자' 다리다 — 에이전트가 사용자에게 목록·이유·되돌림을
    보여줄 때 쓴다(읽기전용, 물음도 실행도 없음). 사용자가 '해'라고 하면 그때
    에이전트가 --yes로 다시 부른다. 두 단계 동의가 CLI로 데려다주는 경로.
    """
    if ctx.invoked_subcommand is not None:
        return  # `evolve log` 등 서브커맨드는 그쪽이 처리한다.

    now = _now()
    store = CatalogStore()
    target_skills = skills_dir or paths.claude_skills_dir()
    target_mcp = mcp_config or paths.project_mcp_config_path()

    # 위생 먼저: 오래된 사용 기록을 요약으로 접는다(무손실). 이후 계획이 접힌
    # 요약을 반영한 정확한 통계 위에서 돈다. dry-run은 읽기전용이라 건너뛴다.
    if not dry_run:
        folded = run_compaction(now=now, after_days=DEFAULT_COMPACT_AFTER_DAYS)
        if folded:
            console.print(f"🧾 오래된 사용 기록 {folded}줄을 요약으로 접었어요(습관은 보존).\n")

        # 관문 (다): 실사용이 소스 스테이징을 카탈로그로 진입시킨다. 계획보다
        # 먼저 돌려야 새로 담긴 도구가 이후 조언·추천에 잡힌다(상태 변경이라 dry-run 제외).
        entered = reconcile(
            source_store=CatalogStore(catalog_dir=paths.sources_dir()),
            catalog_store=store,
        )
        if entered:
            joined = ", ".join(entered)
            console.print(
                f"📥 실제로 쓴 도구 {len(entered)}개가 카탈로그에 진입했어요: "
                f"[cyan]{joined}[/cyan]\n"
            )

    memory_store = MemoryStore()
    # 핵심 도구(지속·빈도로 손에 맞은 것)는 drop 제안에서 보호한다 — 오래 안 봐도
    # 안 내림(기억 weight-면역과 같은 정신, 개인화 학습 레인 1). 신호 없는 종류
    # (훅·규칙·에이전트)는 "안 쓰임"을 판별할 수 없어 애초에 후보에서 뺀다.
    core = core_entry_ids(read_events(), alias_map=alias_map(list(store.list())))
    drops = [
        d for d in plan_evolution(now=now, config=EvolveConfig())
        if has_usage_signal(store.get(d.entry_id)) and d.entry_id not in core
    ]
    attaches = plan_attach(now=now, store=store)
    # (A→B) plugin 관측 사용을 조언으로 — pouch가 안 바꾸고 소유자에게 안내만.
    advice = plan_plugin_advice(now=now, store=store, config=EvolveConfig())
    pending = plan_memory_pending(memory_store)
    hygiene = plan_memory_hygiene(memory_store, now=datetime.now().date())
    if not drops and not attaches and not advice and not pending and not hygiene:
        console.print("🌊 오르내릴 것이 없습니다. 주머니가 손에 맞게 유지되고 있어요.")
        return

    active_ids = set(active_entries())  # '이거 써봐'가 이미 켠 것을 다시 안 권하게

    if dry_run:
        _preview_plan(
            drops, attaches, advice, pending, hygiene, store=store, active_ids=active_ids
        )
        return

    if drops:
        _propose_drops(
            drops, yes=yes, store=store,
            skills_dir=target_skills, mcp_config_path=target_mcp,
        )
    if attaches or advice:
        _propose_attaches(
            attaches, yes=yes, store=store,
            skills_dir=target_skills, mcp_config_path=target_mcp,
            active_ids=active_ids, advice=advice,
        )
    if pending:
        _propose_memory_pending(pending, yes=yes, store=memory_store)
    if hygiene:
        _propose_memory_hygiene(hygiene, yes=yes, store=memory_store)


def _render_advice(advice: list[Advice]) -> None:
    """plugin 관측 사용에 대한 조언을 사람 말로 보여준다(A→B: 행위 아니라 조언).

    pouch는 표면을 강제로 안 바꾼다 — 소유자(ECC/사용자)에게 안내만. reinforce는
    "잘 쓰고 계세요"(그대로), suggest_off는 "요즘 안 쓰시네요, ECC에서 꺼볼까요"
    (pouch가 직접 안 내림). observe의 죽은 "관측만" 줄을 이 조언이 대체한다.
    """
    if not advice:
        return
    console.print("\n🔌 [bold]플러그인 도구[/bold] (표면은 ECC가 관리 — pouch는 안내만)\n")
    for a in advice:
        if a.kind == "reinforce":
            console.print(
                f"  ● [cyan]{a.target}[/cyan] — 잘 쓰고 계세요 (최근 {a.count}회). 그대로 두세요."
            )
        else:  # suggest_off
            console.print(
                f"  ○ [cyan]{a.target}[/cyan] — 요즘 안 쓰시네요. "
                "ECC에서 꺼도 될 것 같아요 [dim](pouch가 직접 내리진 않아요)[/dim]."
            )


def _preview_plan(
    drops: list[DropCandidate],
    attaches: list[AttachCandidate],
    advice: list[Advice],
    pending: list[MemoryEntry],
    hygiene: list[HygieneCandidate],
    *,
    store: CatalogStore,
    active_ids: set[str],
) -> None:
    """읽기전용 목록 — 항목마다 효과+되돌림(preview 단일 출처). 실행·물음 없음.

    '정리하자'에 에이전트가 이걸 사용자에게 보여준다. 되돌림 한 줄까지 여기서
    나오므로 에이전트가 결과를 지어낼 수 없다(조각 2 자물쇠의 회수). 실행하려면
    사용자 동의를 받아 [cyan]pouch evolve --yes[/cyan]로 다시 부른다.
    """
    console.print("🌊 [bold]정리 예고[/bold] — 아래는 제안일 뿐, 아직 아무것도 하지 않았습니다.\n")

    for cand in drops:
        pv = preview_drop(cand)
        reason = _REASON_LABEL.get(cand.reason, cand.reason)
        console.print(f"  ▽ [cyan]{pv.target}[/cyan] 내리기 — {reason}")
        console.print(f"     {pv.effect}")
        console.print(f"     되돌리기: [cyan]{pv.undo}[/cyan]")

    # observe(plugin 관측)는 이제 advice가 대체한다 — 여기선 reattach·adopt만.
    for cand in attaches:
        if cand.kind == "observe":
            continue
        pv = preview_attach(cand)
        arrow = {"reattach": "△", "adopt": "＋"}.get(pv.action, "•")
        console.print(f"  {arrow} [cyan]{pv.target}[/cyan] {pv.action} — 최근 {cand.count}회 씀")
        console.print(f"     {pv.effect}")
        if pv.undo:
            console.print(f"     되돌리기: [cyan]{pv.undo}[/cyan]")

    _render_advice(advice)

    for entry in pending:
        console.print(f"  ＋ [cyan]{entry.name}[/cyan] 기억 확인 — {entry.description}")
        console.print("     인덱스에 올립니다(pending → indexed).")
    for cand in hygiene:
        console.print(f"  ▽ [cyan]{cand.name}[/cyan] 기억 정리 — {cand.detail}")
        console.print("     인덱스에서 내립니다(파일은 남음, recall로 되찾음).")

    # '이거 써봐' — 반복 앵커 곁에 비슷한 후보도(읽기전용이라 여기서도 안전).
    _render_try_this(attaches, store=store, active_ids=active_ids)

    console.print(
        "\n실행하려면: [cyan]pouch evolve --yes[/cyan] "
        "(또는 대화형으로 [cyan]pouch evolve[/cyan])."
    )


def _render_try_this(
    attaches: list[AttachCandidate], *, store: CatalogStore, active_ids: set[str]
) -> None:
    """반복 앵커 곁에 '비슷한 후보도 이거'를 붙여 보여준다('이거 써봐' 조각 3).

    앵커 = 반복 신호(reattach·adopt)의 도구 — 새 발견 로직 아님, 있는 신호 재사용.
    비슷함은 태그 겹침으로만(지어내기 없음), 왜 비슷한지(겹친 태그)를 함께 보여준다.
    붙일 게 없으면(날것 예외·겹침 0) 조용히 아무것도 안 그린다(소음 0).
    """
    anchor_ids = [c.entry_id for c in attaches if c.kind in ("reattach", "adopt")]
    plans = plan_try_this(anchor_ids, list(store.list()), active_ids=active_ids)
    if not plans:
        return

    console.print("\n💡 [bold]이거 써봐[/bold] (자주 쓰시는 것과 비슷한 것들)\n")
    for plan in plans:
        console.print(f"  [dim]{plan.anchor_id}와 비슷:[/dim]")
        for cand in plan.similar:
            shared = ", ".join(sorted(cand.shared_tokens))
            console.print(
                f"    • [cyan]{cand.entry.id}[/cyan] — {cand.entry.description}"
                f" [dim](비슷한 점: {shared})[/dim]"
            )


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
    console.print(f"\n[green]✓[/green] {len(dropped)}개 내렸습니다:")
    # 되돌리는 정확한 한 줄은 preview(단일 출처)에서 나온다 — 산문으로 짓지 않는다.
    for cand in candidates:
        if cand.entry_id not in dropped:
            continue
        undo = preview_drop(cand).undo
        console.print(f"   • [cyan]{cand.entry_id}[/cyan] — 되돌리기: [cyan]{undo}[/cyan]")

    for entry_id in dropped:
        _gate_boundaries_for_dropped(entry_id)


def _gate_boundaries_for_dropped(entry_id: str) -> None:
    """내려간 도구가 딸고 왔던 boundary를 방향으로 가른다(P1 drop gate).

    allow는 도구와 함께 강등(허용은 좁게), ask·deny·방향불명은 잔존+경고
    (금지·확인은 넓게 — 사라지는 게 위험). 사람이 건 것은 애초에 대상이 아니다.
    """
    mstore = MemoryStore()
    plan = plan_boundary_drop(list(mstore.list()), entry_id)
    for mem in plan.to_demote:
        mstore.demote(mem)
        console.print(
            f"   [dim]· 경계 '{mem.name}'(allow)를 함께 내렸습니다 — 도구와 짝.[/dim]"
        )
    for mem in plan.to_keep:
        console.print(
            f"   [yellow]⚑[/yellow] 경계 '{mem.name}'"
            f"[{mem.direction.value if mem.direction else '?'}]는 남겼습니다 — "
            "출처 도구가 내려갔으니 유효성 확인 요망."
        )


def _propose_attaches(
    candidates: list[AttachCandidate],
    *,
    yes: bool,
    store: CatalogStore,
    skills_dir: Path,
    mcp_config_path: Path,
    active_ids: set[str],
    advice: list[Advice],
) -> None:
    """당겨올 후보를 보여준다 — reattach는 동의 시 실행, adopt는 안내만.

    plugin 관측(observe)은 이제 advice가 대체한다(A→B: 관측만이 아니라 조언).
    """
    reattaches = [c for c in candidates if c.kind == "reattach"]
    adopts = [c for c in candidates if c.kind == "adopt"]

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

    # plugin 관측 사용 → 조언(행위 아님, 소유자에게 안내만).
    _render_advice(advice)

    # '이거 써봐' — 반복 앵커 곁에 비슷한 후보도(안내만, 실행 아님).
    _render_try_this(candidates, store=store, active_ids=active_ids)

    if not reattaches:
        return
    if not yes and not typer.confirm("\n표면에 다시 올릴까요?", default=False):
        console.print("그대로 두었습니다.")
        return

    restored_cands: list[AttachCandidate] = []
    for cand in reattaches:
        try:
            if apply_reattach(
                cand.entry_id, store=store,
                skills_dir=skills_dir, mcp_config_path=mcp_config_path,
            ):
                restored_cands.append(cand)
        except (ValueError, FileNotFoundError) as exc:
            console.print(f"  [red]✗[/red] {cand.entry_id}: {exc}")
    if restored_cands:
        console.print(f"\n[green]✓[/green] {len(restored_cands)}개 다시 올렸습니다:")
        # 되돌리는 한 줄은 preview(단일 출처)에서 — 산문으로 짓지 않는다.
        for cand in restored_cands:
            undo = preview_attach(cand).undo
            console.print(f"   • [cyan]{cand.entry_id}[/cyan] — 되돌리기: [cyan]{undo}[/cyan]")


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
