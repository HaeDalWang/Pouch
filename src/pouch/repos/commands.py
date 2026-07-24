"""`pouch repo` 서브커맨드 — 도구 저장소 등록 관리 (Phase 4.8 조각 ①).

helm과 같은 손맛: add <이름> <주소> / list / remove <이름>. 등록까지만 한다 —
색인·추천·설치는 다음 조각들이 이 위에 얹는다.
"""

from __future__ import annotations

import typer
from rich.console import Console

from pouch import paths
from pouch.repos.manage import RepoError, add_repo, list_repos, remove_repo

app = typer.Typer(
    help="🗄️ repo — 도구 저장소 주소를 물어둔다 (helm repo처럼).",
    no_args_is_help=True,
)
console = Console()


@app.command("add")
def add(
    name: str = typer.Argument(..., help="저장소를 부를 이름(폴더 이름이 됩니다)."),
    url: str = typer.Argument(..., help="git 주소 (GitHub 주소 등)."),
) -> None:
    """주소를 등록한다. 다시 add하면 갱신(pull) — helm repo add처럼 멱등.

    등록은 신뢰 표명이다: 어느 주소를 물릴지는 사용자가 고른다(pouch가 기본
    저장소를 미리 물려두지 않는 이유). 등록만으로는 아무것도 설치·실행되지 않는다.
    """
    try:
        info = add_repo(name, url, repos_dir=paths.repos_dir())
    except RepoError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]✓[/green] 저장소 [cyan]{info.name}[/cyan] ← {info.url}\n"
        "   등록만 했습니다 — 설치·실행된 것은 없습니다."
    )


@app.command("list")
def list_() -> None:
    """등록된 저장소 목록. 처음엔 빈손이 정상입니다(기본 저장소 없음)."""
    repos = list_repos(repos_dir=paths.repos_dir())
    if not repos:
        console.print(
            "🗄️ 등록된 저장소가 없습니다.\n"
            "   등록: [cyan]pouch repo add <이름> <git주소>[/cyan]"
        )
        return
    console.print(f"🗄️ [bold]등록된 저장소[/bold] ({len(repos)}개)\n")
    for repo in repos:
        console.print(f"  • [cyan]{repo.name}[/cyan] ← {repo.url or '?'}")


@app.command("remove")
def remove(
    name: str = typer.Argument(..., help="등록을 지울 저장소 이름."),
) -> None:
    """등록을 지운다(받아둔 사본 삭제). 되돌리기는 add 한 번."""
    try:
        removed = remove_repo(name, repos_dir=paths.repos_dir())
    except RepoError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc
    if not removed:
        console.print(f"🗄️ '{name}'은 등록돼 있지 않습니다.")
        return
    console.print(
        f"[green]✓[/green] [cyan]{name}[/cyan] 등록을 지웠습니다 "
        "(주소만 알면 언제든 다시 add)."
    )
