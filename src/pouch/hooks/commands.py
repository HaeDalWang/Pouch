"""`pouch hook` 서브커맨드 — 자동화하되 투명하게 연결한다.

기본 동작은 사람 말 설명 + 동의 + 백업. `--yes`로 완전 자동도 지원한다.
비기술직군이 json을 열지 않고도 쓸 수 있어야 한다는 원칙을 따른다.

호스트 어댑터 계층 위에 얹혀 있다: `--host`를 주면 그 에이전트 하나를, 안 주면
이 머신에 설정 파일이 있는 호스트 전체를 대상으로 삼는다(탐지). 배선 스키마의
차이는 어댑터가 흡수하므로 이 계층은 "걸까/걷을까"만 결정한다.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from pouch.hosts.base import HostAdapter
from pouch.hosts.registry import (
    adapter_names,
    all_adapters,
    detect_installed,
    get_adapter,
)

app = typer.Typer(
    help="🔌 hook — pouch를 에이전트(Claude Code·Codex·Kiro)에 연결.",
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
  • 각 에이전트 설정에 연결 두 줄을 추가합니다 (당신이 json을 열 필요 없음).
  • 기존 설정은 그대로 두고, 되돌릴 수 있게 백업(.bak)을 남깁니다.
  • 언제든 [cyan]pouch hook uninstall[/cyan] 로 원상복구할 수 있습니다.
"""


def _fully_installed(adapter: HostAdapter, config: dict) -> bool:
    """두 배선(기억 주입 + 사용 로깅)이 모두 걸려 있는지."""
    return adapter.is_memory_installed(config) and adapter.is_usage_installed(config)


def _resolve_targets(host: str | None) -> list[HostAdapter]:
    """`--host` 값을 대상 어댑터 목록으로 푼다.

    지정하면 그 하나(모르는 이름이면 종료), 안 하면 설치된 호스트 전체.
    설치된 게 하나도 없으면 빈 리스트(호출부가 안내).
    """
    if host is not None:
        adapter = get_adapter(host)
        if adapter is None:
            names = ", ".join(adapter_names())
            console.print(f"[red]모르는 호스트:[/red] {host}  (가능: {names})")
            raise typer.Exit(code=1)
        return [adapter]
    return detect_installed()


@app.command("install")
def install(
    host: str | None = typer.Option(
        None, "--host", help="연결할 에이전트(claude·codex·kiro). 생략 시 감지된 전체."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="설명·확인 없이 바로 설치."),
) -> None:
    """기억 주입(세션 시작) + 사용 로깅(도구 호출) 배선을 추가한다(멱등)."""
    targets = _resolve_targets(host)
    if not targets:
        console.print("연결할 에이전트를 찾지 못했습니다(설정 파일 없음).")
        console.print(f"[cyan]--host[/cyan] 로 직접 지정할 수 있습니다: {', '.join(adapter_names())}")
        return

    if not yes:
        console.print(_EXPLAIN)
        names = ", ".join(a.display_name for a in targets)
        if not typer.confirm(f"연결 대상: {names}\n진행할까요?", default=True):
            console.print("취소했습니다.")
            raise typer.Exit()

    for adapter in targets:
        _install_one(adapter)


def _install_one(adapter: HostAdapter) -> None:
    """한 호스트에 두 배선을 건다. 이미 완료면 조용히 표시."""
    path = adapter.config_path()
    config = adapter.load(path)
    if _fully_installed(adapter, config):
        console.print(f"[green]✓[/green] {adapter.display_name}: 이미 연결돼 있습니다.")
        return
    updated = adapter.with_usage_installed(adapter.with_memory_installed(config))
    backup = adapter.write(path, updated)
    console.print(f"[green]✓[/green] {adapter.display_name} 연결 완료 → {path}")
    if backup:
        console.print(f"   백업: {backup}")
    for note in adapter.post_install_notes():
        console.print(f"   [yellow]![/yellow] {escape(note)}")


@app.command("uninstall")
def uninstall(
    host: str | None = typer.Option(
        None, "--host", help="해제할 에이전트(claude·codex·kiro). 생략 시 감지된 전체."
    ),
) -> None:
    """추가했던 두 배선(기억 주입 + 사용 로깅)을 모두 제거한다."""
    targets = _resolve_targets(host)
    if not targets:
        console.print("연결된 에이전트를 찾지 못했습니다.")
        return
    for adapter in targets:
        _uninstall_one(adapter)


def _uninstall_one(adapter: HostAdapter) -> None:
    """한 호스트에서 두 배선을 걷어낸다. 안 걸려 있으면 조용히 표시."""
    path = adapter.config_path()
    config = adapter.load(path)
    if not adapter.is_memory_installed(config) and not adapter.is_usage_installed(config):
        console.print(f"[dim]○[/dim] {adapter.display_name}: 연결돼 있지 않습니다.")
        return
    updated = adapter.with_usage_removed(adapter.with_memory_removed(config))
    backup = adapter.write(path, updated)
    console.print(f"[green]✓[/green] {adapter.display_name} 연결 해제 완료 → {path}")
    if backup:
        console.print(f"   백업: {backup}")


@app.command("status")
def status() -> None:
    """호스트별 연결 상태를 두 축(기억 주입 / 사용 로깅)으로 보여준다."""
    for adapter in all_adapters():
        config = adapter.load(adapter.config_path())
        mem = _dot(adapter.is_memory_installed(config))
        usage = _dot(adapter.is_usage_installed(config))
        console.print(f"[bold]{adapter.display_name}[/bold]  기억 주입: {mem}   사용 로깅: {usage}")
    console.print("[cyan]pouch hook install[/cyan] 로 감지된 에이전트에 연결하세요.")


def _dot(installed: bool) -> str:
    return "[green]●[/green] 연결됨" if installed else "[dim]○[/dim] 안 됨"
