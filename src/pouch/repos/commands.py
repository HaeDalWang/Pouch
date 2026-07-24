"""`pouch repo` 서브커맨드 — 도구 저장소 등록 관리 (Phase 4.8 조각 ①).

helm과 같은 손맛: add <이름> <주소> / list / remove <이름>. 등록까지만 한다 —
색인·추천·설치는 다음 조각들이 이 위에 얹는다.
"""

from __future__ import annotations

import typer
from rich.console import Console

from pouch import paths
from pouch.repos.index import index_repo, indexed_count, search_index
from pouch.repos.manage import RepoError, add_repo, list_repos, remove_repo
from pouch.textview import clip

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
    from datetime import datetime

    try:
        info = add_repo(name, url, repos_dir=paths.repos_dir())
    except RepoError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]✓[/green] 저장소 [cyan]{info.name}[/cyan] ← {info.url}\n"
        "   등록만 했습니다 — 설치·실행된 것은 없습니다."
    )

    # 색인(조각 ②) — helm이 add 때 index를 받아오듯, 받아둔 사본을 훑어 목록만 만든다.
    report = index_repo(
        info.name,
        info.path,
        index_dir=paths.repo_index_root() / info.name,
        synced_at=datetime.now().isoformat(timespec="seconds"),
    )
    if report.found:
        console.print(f"   색인: 도구 [bold]{report.found}[/bold]개를 알아봤습니다.")
    else:
        console.print(
            "   색인: 아는 배치(skills/·agents/·commands/·rules/·.mcp.json)를 "
            "못 찾았습니다 — 등록은 유지됩니다."
        )
    for reason in report.skipped[:3]:
        console.print(f"   [yellow]⚠[/yellow] 건너뜀: {reason}")
    if len(report.skipped) > 3:
        console.print(f"   [dim]… 건너뛴 것 {len(report.skipped) - 3}개 더[/dim]")


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
        count = indexed_count(paths.repo_index_root() / repo.name)
        console.print(
            f"  • [cyan]{repo.name}[/cyan] — 도구 {count}개 ← {repo.url or '?'}"
        )


@app.command("search")
def search(
    query: str = typer.Argument(
        "", help="찾을 말(이름·제목·설명에서 부분 일치). 비우면 전부."
    ),
) -> None:
    """등록한 저장소들의 색인을 뒤진다 — helm search repo의 pouch판.

    빈손이어도 쓸 수 있는 입구다: 근거는 사용 기록이 아니라 "이 저장소가 담고
    있다"는 실재 사실뿐. 보기만 한다 — 설치·진입 없음.
    """
    hits = search_index(paths.repo_index_root(), query)
    if not hits:
        if not list_repos(repos_dir=paths.repos_dir()):
            console.print(
                "🗄️ 등록된 저장소가 없습니다 — 먼저 "
                "[cyan]pouch repo add <이름> <git주소>[/cyan] 하세요."
            )
        elif query:
            console.print(f"🔍 '{query}'에 걸리는 도구가 색인에 없습니다.")
        else:
            console.print("🔍 색인이 비어 있습니다 — 저장소에 아는 배치가 없었습니다.")
        return
    label = f"'{query}' 검색 결과" if query else "색인 전체"
    console.print(f"🔍 [bold]{label}[/bold] ({len(hits)}개)\n")
    for entry in hits:
        console.print(
            f"  • [cyan]{entry.id}[/cyan] ({entry.kind.value})"
            f" — {clip(entry.description) or '설명 없음'}"
        )


@app.command("remove")
def remove(
    name: str = typer.Argument(..., help="등록을 지울 저장소 이름."),
) -> None:
    """등록을 지운다(받아둔 사본·색인 삭제). 되돌리기는 add 한 번."""
    import shutil

    try:
        removed = remove_repo(name, repos_dir=paths.repos_dir())
    except RepoError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc
    if not removed:
        console.print(f"🗄️ '{name}'은 등록돼 있지 않습니다.")
        return
    # 색인은 클론의 파생물 — 클론이 가면 같이 간다(유령 방지).
    index_dir = paths.repo_index_root() / name
    if index_dir.exists():
        shutil.rmtree(index_dir)
    console.print(
        f"[green]✓[/green] [cyan]{name}[/cyan] 등록을 지웠습니다 "
        "(주소만 알면 언제든 다시 add)."
    )
