"""pouch CLI 진입점.

Phase 0 골격: `pouch`, `pouch --version`, `pouch --help` 만 동작한다.
이후 Phase 1부터 `pouch memory …` 등의 서브커맨드가 여기에 붙는다.
"""

from __future__ import annotations

import typer
from rich.console import Console

from pouch import __version__
from pouch.backup.commands import backup as backup_command
from pouch.backup.commands import restore as restore_command
from pouch.boundary.commands import app as boundary_app
from pouch.catalog.commands import app as catalog_app
from pouch.checkpoint.commands import app as checkpoint_app
from pouch.evolution.commands import app as evolve_app
from pouch.hooks.commands import app as hook_app
from pouch.init.commands import init as init_command
from pouch.memory.commands import app as memory_app
from pouch.sets.commands import app as sets_app

app = typer.Typer(
    name="pouch",
    help="🦦 pouch — 나에게 맞춰지고, 쓸수록 진화하는 개인 하네스.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()

app.add_typer(memory_app, name="memory", help="🧠 메모리 — 쓸수록 쌓이는 개인 기억.")
app.add_typer(boundary_app, name="boundary", help="🚧 경계 — 자율성의 허용·확인·금지.")
app.add_typer(catalog_app, name="catalog", help="📦 catalog — 주머니에 담을 수 있는 것의 레지스트리.")
app.add_typer(hook_app, name="hook", help="🔌 에이전트 연결(hook) 관리.")
app.add_typer(evolve_app, name="evolve", help="🌊 evolve — 쓸수록 손에 맞게, 안 쓰는 건 정리.")
app.add_typer(checkpoint_app, name="checkpoint", help="🎯 정렬 체크포인트 — 이번 작업 목표를 고정한다.")
app.add_typer(sets_app, name="set", help="🎒 set — 미리 꾸려진 한 벌(시작 세트).")
app.command(name="init", help="🪨 환경을 감지하고 나에게 맞춰 주머니를 채운다.")(init_command)
app.command(name="backup", help="💾 전역 주머니를 아카이브로 백업한다.")(backup_command)
app.command(name="restore", help="💾 백업 아카이브로 주머니를 되돌린다.")(restore_command)


def _version_callback(value: bool) -> None:  # noqa: FBT001
    """`--version` 처리: 버전만 출력하고 즉시 종료."""
    if value:
        console.print(f"pouch {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    show_version: bool = typer.Option(  # noqa: FBT001
        False,
        "--version",
        "-V",
        help="버전을 출력하고 종료합니다.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """서브커맨드가 없으면 현재 주머니 상태를 보여준다."""
    if ctx.invoked_subcommand is None:
        _show_status()


def _show_status() -> None:
    """현재 주머니 상태를 한 화면으로 보여준다(시계는 이 경계에서만 읽는다)."""
    from datetime import datetime

    from pouch.status import gather_status, render_lines

    now = datetime.now().isoformat(timespec="seconds")
    for line in render_lines(gather_status(now=now)):
        console.print(line)
    console.print("\n   도움말: [dim]pouch --help[/dim]")
