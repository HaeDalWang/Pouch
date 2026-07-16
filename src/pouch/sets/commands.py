"""`pouch set` 서브커맨드 + init이 부르는 세트 제안 — 온보딩의 입구.

세트는 통째로 제안하고 통째로 동의받는다(개별 물음 없음). 단 훅이 올라갔으면
실행될 명령 원문을 항상 출력한다 — --yes여도 출력은 남는다(배승도 결정).
"""

from __future__ import annotations

import json
from datetime import datetime

import typer
from rich.console import Console

from pouch import paths
from pouch.catalog.model import ToolKind
from pouch.catalog.store import CatalogStore
from pouch.sets.apply import SetApplyReport, apply_set
from pouch.sets.model import StarterSet, available_sets, load_set_file, match_sets

app = typer.Typer(
    help="🎒 set — 미리 꾸려진 한 벌(시작 세트).",
    no_args_is_help=True,
)
console = Console()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@app.command("list")
def list_sets() -> None:
    """쓸 수 있는 세트를 보여준다(내장 + ~/.pouch/sets/)."""
    sets = available_sets()
    if not sets:
        console.print("🎒 쓸 수 있는 세트가 없습니다.")
        return
    console.print(f"🎒 [bold]시작 세트[/bold] ({len(sets)}개)\n")
    for starter in sets:
        install_count = sum(len(item.install) for item in starter.items)
        console.print(
            f"  • [cyan]{starter.name}[/cyan] — {starter.title}"
            f" [dim](올릴 것 {install_count}개)[/dim]"
        )
        if starter.description:
            console.print(f"    {starter.description}")
    console.print("\n   적용: [cyan]pouch set apply <이름>[/cyan]")


@app.command("apply")
def apply(
    name: str = typer.Argument(..., help="적용할 세트 이름."),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 없이 적용."),
) -> None:
    """세트를 통째로 적용한다 — 출처에서 가져와 담고, 고른 것을 표면에 올린다."""
    starter = next((s for s in available_sets() if s.name == name), None)
    if starter is None:
        console.print(f"[red]✗[/red] '{name}' 세트가 없습니다. [cyan]pouch set list[/cyan]로 확인하세요.")
        raise typer.Exit(code=1)
    run_set_apply(starter, yes=yes)


@app.command("import")
def import_set(
    path: str = typer.Argument(..., help="가져올 세트 JSON 경로."),
    yes: bool = typer.Option(False, "--yes", "-y", help="같은 이름 덮어쓰기 확인 생략."),
) -> None:
    """남이 굳힌 세트 파일을 내 주머니로 들인다 → ~/.pouch/sets/<이름>.json.

    세트는 매니페스트(선곡표)라 코드가 아니다 — 들이기만으로는 아무것도 실행·설치되지
    않는다. 실제 적용은 `pouch set apply <이름>`이 하고 동의는 거기서 받는다(raft의
    첫 문: 남이 굳힌 것을 받는 쪽). 파일이 세트 형식인지 검증하고, 이름으로 정규화해
    저장한다 — 그래야 곧장 `set list`/`apply`에 잡힌다.
    """
    from pathlib import Path

    src = Path(path).expanduser()
    if not src.is_file():
        console.print(f"[red]✗[/red] 파일이 없습니다: {src}")
        raise typer.Exit(code=1)
    try:
        starter = load_set_file(src)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        console.print(f"[red]✗[/red] 세트 파일이 아닙니다({src}): {exc}")
        raise typer.Exit(code=1) from exc

    dest = paths.sets_dir() / f"{starter.name}.json"
    if dest.exists() and not yes and not typer.confirm(
        f"같은 이름 세트가 있습니다 — {dest}를 덮어쓸까요?", default=False
    ):
        console.print("들이지 않았습니다.")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    install_total = sum(len(item.install) for item in starter.items)
    console.print(
        f"[green]✓[/green] [cyan]{starter.name}[/cyan] 세트를 들였습니다 — {starter.title}"
        f" [dim](출처 {len(starter.items)}곳, 올릴 것 {install_total}개)[/dim]"
    )
    # 정직한 보고: 이 컴퓨터에 없는 출처는 apply 때 건너뛴다(인질 금지와 같은 정신).
    missing = [
        item.source for item in starter.items if not Path(item.source).expanduser().exists()
    ]
    if missing:
        console.print(
            f"  [yellow]![/yellow] 출처 {len(missing)}곳이 이 컴퓨터에 없어 apply 때 건너뜁니다:"
        )
        for source in missing:
            console.print(f"     [dim]{source}[/dim]")
    console.print(f"\n   적용: [cyan]pouch set apply {starter.name}[/cyan]")


def run_set_apply(starter: StarterSet, *, yes: bool) -> SetApplyReport | None:
    """세트 제안 → 동의 → 적용 → 사람 말 보고. init도 이 경로를 그대로 쓴다."""
    install_total = sum(len(item.install) for item in starter.items)
    console.print(f"\n🎒 [bold]{starter.title}[/bold]")
    if starter.description:
        console.print(f"   {starter.description}")
    console.print(
        f"   출처 {len(starter.items)}곳에서 가져와, {install_total}개를 표면에 올립니다."
    )
    if not yes and not typer.confirm("이 세트로 시작할까요?", default=True):
        console.print("적용하지 않았습니다.")
        return None

    store = CatalogStore()
    report = apply_set(
        starter, store,
        skills_dir=paths.claude_skills_dir(),
        mcp_config_path=paths.project_mcp_config_path(),
        synced_at=_now(),
    )
    _render_report(report, store)
    return report


def _render_report(report: SetApplyReport, store: CatalogStore) -> None:
    console.print(
        f"[green]✓[/green] {report.imported}개를 카탈로그에 담고,"
        f" {len(report.installed)}개를 표면에 올렸습니다."
    )
    for entry_id in report.installed:
        console.print(f"  • [cyan]{entry_id}[/cyan]")
    # 훅은 명령을 실행하므로 무엇이 배선됐는지 원문을 항상 남긴다(--yes여도).
    for entry_id in report.installed:
        entry = store.get(entry_id)
        if entry is None or entry.kind is not ToolKind.HOOK:
            continue
        recipe = entry.recipe or {}
        where = recipe.get("event", "?")
        if recipe.get("matcher"):
            where += f" ({recipe['matcher']})"
        console.print(f"  ⚡ [cyan]{entry_id}[/cyan] — {where} 때마다 실행:")
        for hook in recipe.get("hooks", []):
            console.print(f"     [yellow]$ {hook.get('command', '')}[/yellow]")
    for reason in report.skipped:
        console.print(f"  [yellow]![/yellow] {reason}")


def offer_matching_set(*, tokens: set[str], yes: bool) -> bool:
    """관심 토큰에 맞는 세트가 있으면 가장 잘 맞는 하나를 제안한다(init 경로).

    적용(또는 시도)했으면 True, 맞는 세트가 없으면 False — 호출부(init)가
    False일 때 기존 낱개 추천 흐름을 그대로 탄다.
    """
    matches = match_sets(available_sets(), tokens=tokens)
    if not matches:
        return False
    run_set_apply(matches[0], yes=yes)
    return True
