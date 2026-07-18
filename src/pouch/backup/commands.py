"""`pouch backup` / `pouch restore` — 잃었을 때 되찾기.

백업은 비파괴적이라 바로 실행한다. 복원은 현재 `~/.pouch`를 백업 시점으로
덮으므로(파괴적) 기본은 설명 + 확인을 거치고, 복원 직전 현재 상태를 자동
스냅샷으로 남긴다. `--yes`로 확인을 건너뛸 수 있어도 스냅샷은 건너뛰지 않는다.

v0 목적지는 로컬 폴더뿐. S3·구글드라이브는 같은 계약으로 이 위에 얹는다.
시계(now)는 이 경계에서만 읽는다 — 코어·어댑터는 결정적으로 유지.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from pouch.confirm import confirm
from pouch import paths
from pouch.backup.local import backup_to_local, restore_from_local

console = Console()


def _has_content(directory: Path) -> bool:
    return directory.is_dir() and any(directory.iterdir())


def backup(
    to: Path = typer.Option(
        None, "--to", help="백업을 놓을 폴더(기본: ~/pouch-backups/)."
    ),
) -> None:
    """전역 주머니(`~/.pouch`)를 타임스탬프 아카이브 하나로 싼다."""
    source = paths.global_root()
    if not _has_content(source):
        console.print("[yellow]![/yellow] 백업할 주머니가 아직 없습니다 (~/.pouch 비어있음).")
        raise typer.Exit()

    dest = to.expanduser() if to else paths.backup_dir()
    now = datetime.now().isoformat(timespec="seconds")
    archive = backup_to_local(source, dest, now=now)
    console.print(f"[green]✓[/green] 백업 완료 → {archive}")
    console.print(f"   되돌리려면: [cyan]pouch restore {archive}[/cyan]")


def restore(
    archive: Path = typer.Argument(..., help="복원할 백업 아카이브(.tar.gz) 경로."),
    yes: bool = typer.Option(False, "--yes", "-y", help="설명·확인 없이 바로 복원."),
) -> None:
    """아카이브를 전역 주머니(`~/.pouch`)로 복원한다(현재 상태는 스냅샷 후 덮음)."""
    archive = archive.expanduser()
    if not archive.is_file():
        console.print(f"[red]✗[/red] 아카이브를 찾을 수 없습니다: {archive}")
        raise typer.Exit(code=1)

    target = paths.global_root()
    if not yes:
        console.print(
            "[bold]💾 주머니를 이 백업으로 되돌립니다.[/bold]\n\n"
            f"  • 현재 [cyan]{target}[/cyan] 의 내용이 백업 시점으로 바뀝니다.\n"
            "  • 덮기 전에 지금 상태를 스냅샷으로 남깁니다 (복원의 되돌리기).\n"
            "  • 백업 후 새로 생긴 파일은 사라지지만, 스냅샷 안에 살아있습니다."
        )
        if not confirm("복원할까요?", default=False):
            console.print("취소했습니다.")
            raise typer.Exit()

    now = datetime.now().isoformat(timespec="seconds")
    snapshot = restore_from_local(
        archive, target, snapshot_dir=paths.backup_dir(), now=now
    )
    console.print(f"[green]✓[/green] 복원 완료 → {target}")
    if snapshot:
        console.print(f"   복원 직전 스냅샷: {snapshot}")
