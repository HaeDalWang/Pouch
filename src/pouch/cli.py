"""pouch CLI 진입점.

Phase 0 골격: `pouch`, `pouch --version`, `pouch --help` 만 동작한다.
이후 Phase 1부터 `pouch memory …` 등의 서브커맨드가 여기에 붙는다.
"""

from __future__ import annotations

import typer
from rich.console import Console

from pouch import __version__

app = typer.Typer(
    name="pouch",
    help="🦦 pouch — 나에게 맞춰지고, 쓸수록 진화하는 개인 하네스.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()


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
    """아직 비어있는 주머니의 현재 상태와 다음 단계를 안내한다."""
    console.print("🦦 [bold]pouch[/bold] — 아직 비어있는 주머니")
    console.print("   다음 단계: [cyan]Phase 1 — 메모리 레이어[/cyan]")
    console.print("   도움말:   [dim]pouch --help[/dim]")
