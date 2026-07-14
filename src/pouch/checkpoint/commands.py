"""`pouch checkpoint` 서브커맨드 — 에이전트가 한 줄로 호출하는 비대화형 인터페이스.

set은 이번 작업 목표를 고정하고, show는 ◆목표 슬롯에 붙일 값을 평문으로 뱉는다
(에이전트가 그대로 재사용). clear는 작업 끝에 앵커를 비운다. 시계는 set 경계에서만
읽는다(anchor 사이드카가 이벤트 시각을 소유).
"""

from __future__ import annotations

import typer
from rich.console import Console

from pouch.checkpoint.anchor import clear_anchor, load_anchor, set_anchor

app = typer.Typer(
    help="🎯 정렬 체크포인트 — 이번 작업 목표를 고정한다.",
    no_args_is_help=True,
)
console = Console()


@app.command("set")
def set_goal(
    goal: str = typer.Argument(..., help="이번 작업의 목표 한 줄."),
) -> None:
    """이번 작업 목표를 앵커로 고정한다(기존 앵커는 덮어쓴다).

    작업을 시작할 때 사용자의 첫 지시에서 목표 한 줄을 뽑아 부른다. 이후 요약의
    ◆목표 슬롯은 이 값을 그대로 재사용한다(재서술 금지 — 고정점).
    """
    from datetime import datetime

    now = datetime.now().isoformat(timespec="seconds")
    anchor = set_anchor(goal, now=now)
    console.print(f"[green]✓[/green] 이번 목표 고정: [bold]{anchor.goal}[/bold]")


@app.command("show")
def show_goal() -> None:
    """고정된 목표 문자열만 평문으로 출력한다(◆목표 슬롯에 붙일 값).

    앵커가 없으면 아무것도 출력하지 않는다(빈 출력).
    """
    anchor = load_anchor()
    if anchor is not None:
        typer.echo(anchor.goal, nl=False)


@app.command("clear")
def clear_goal() -> None:
    """앵커를 비운다(작업이 끝났을 때)."""
    if clear_anchor():
        console.print("[green]✓[/green] 이번 목표 앵커를 비웠습니다.")
    else:
        console.print("고정된 목표가 없습니다.")
