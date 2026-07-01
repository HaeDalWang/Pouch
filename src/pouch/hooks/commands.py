"""`pouch hook` 서브커맨드 — 자동화하되 투명하게 연결한다.

기본 동작은 사람 말 설명 + 동의 + 백업. `--yes`로 완전 자동도 지원한다.
비기술직군이 json을 열지 않고도 쓸 수 있어야 한다는 원칙을 따른다.
"""

from __future__ import annotations

import typer
from rich.console import Console

from pouch import paths
from pouch.hooks.settings import (
    is_installed,
    is_usage_hook_installed,
    load_settings,
    with_hook_installed,
    with_hook_removed,
    with_usage_hook_installed,
    with_usage_hook_removed,
    write_settings,
)

app = typer.Typer(
    help="🔌 hook — pouch를 에이전트(Claude Code)에 연결.",
    no_args_is_help=True,
)
console = Console()

_EXPLAIN = """[bold]🦦 pouch를 에이전트에 연결합니다.[/bold]

  [bold]무엇이 바뀌나요?[/bold]
  • 이제 대화를 시작할 때마다, 에이전트가 당신이 누구인지·
    무엇을 기억해뒀는지 알고 시작합니다.
  • 그리고 당신이 어떤 도구를 실제로 쓰는지 조용히 기억해둡니다 —
    나중에 [cyan]pouch evolve[/cyan]가 안 쓰는 도구 정리를 제안할 수 있게.

  [bold]pouch가 대신 해주는 일:[/bold]
  • Claude 설정에 연결 두 줄을 추가합니다 (당신이 json을 열 필요 없음).
  • 기존 설정은 그대로 두고, 되돌릴 수 있게 백업(.bak)을 남깁니다.
  • 언제든 [cyan]pouch hook uninstall[/cyan] 로 원상복구할 수 있습니다.
"""


def _fully_installed(settings: dict) -> bool:
    """두 hook(기억 주입 + 사용 로깅)이 모두 걸려 있는지."""
    return is_installed(settings) and is_usage_hook_installed(settings)


@app.command("install")
def install(
    yes: bool = typer.Option(False, "--yes", "-y", help="설명·확인 없이 바로 설치."),
) -> None:
    """SessionStart(기억 주입) + PostToolUse(사용 로깅) hook을 추가한다(멱등)."""
    path = paths.claude_settings_path()
    settings = load_settings(path)
    if _fully_installed(settings):
        console.print("[green]✓[/green] 이미 연결돼 있습니다.")
        return
    if not yes:
        console.print(_EXPLAIN)
        if not typer.confirm("진행할까요?", default=True):
            console.print("취소했습니다.")
            raise typer.Exit()
    updated = with_usage_hook_installed(with_hook_installed(settings))
    backup = write_settings(path, updated)
    console.print(f"[green]✓[/green] 연결 완료 → {path}")
    if backup:
        console.print(f"   백업: {backup}")
    console.print("   이제 새 세션부터 에이전트가 당신의 기억을 안고 시작합니다.")


@app.command("uninstall")
def uninstall() -> None:
    """추가했던 두 hook(기억 주입 + 사용 로깅)을 모두 제거한다."""
    path = paths.claude_settings_path()
    settings = load_settings(path)
    if not is_installed(settings) and not is_usage_hook_installed(settings):
        console.print("연결돼 있지 않습니다.")
        return
    updated = with_usage_hook_removed(with_hook_removed(settings))
    backup = write_settings(path, updated)
    console.print(f"[green]✓[/green] 연결 해제 완료 → {path}")
    if backup:
        console.print(f"   백업: {backup}")


@app.command("status")
def status() -> None:
    """현재 연결 상태를 두 축(기억 주입 / 사용 로깅)으로 보여준다."""
    settings = load_settings(paths.claude_settings_path())
    mem = "[green]●[/green] 연결됨" if is_installed(settings) else "[dim]○[/dim] 안 됨"
    usage = "[green]●[/green] 연결됨" if is_usage_hook_installed(settings) else "[dim]○[/dim] 안 됨"
    console.print(f"기억 주입: {mem}")
    console.print(f"사용 로깅: {usage}")
    if not _fully_installed(settings):
        console.print("[cyan]pouch hook install[/cyan] 로 연결하세요.")
