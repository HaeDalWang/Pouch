"""`pouch hook` 서브커맨드 — 자동화하되 투명하게 연결한다.

기본 동작은 사람 말 설명 + 동의 + 백업. `--yes`로 완전 자동도 지원한다.
비기술직군이 json을 열지 않고도 쓸 수 있어야 한다는 원칙을 따른다.

두 종류의 호스트를 함께 다룬다:
- 훅 호스트(Claude·Codex): JSON 설정에 명령 훅(기억 주입 + 사용 로깅).
- 파일 호스트(Kiro): 홈에 기억 스냅샷 파일(사용 로깅 없음, 기억 바뀌면 자동 갱신).
지정 없이 부르면 이 머신에 있는 호스트 전체가 대상이다(탐지).
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from pouch.hosts.base import FileHostAdapter, HostAdapter
from pouch.hosts.filesync import render_file_body
from pouch.hosts.registry import (
    all_names,
    detect_file_supported,
    detect_hook_installed,
    file_adapters,
    get_file_adapter,
    get_hook_adapter,
    hook_adapters,
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
  • 각 에이전트 설정에 연결을 추가합니다 (당신이 파일을 열 필요 없음).
  • 기존 설정은 그대로 두고, 되돌릴 수 있게 백업(.bak)을 남깁니다.
  • 언제든 [cyan]pouch hook uninstall[/cyan] 로 원상복구할 수 있습니다.
"""


def _global_memory_body() -> str:
    """파일 호스트에 심을 스냅샷 본문(현재 전역 기억)을 렌더한다."""
    from pouch.memory.store import MemoryStore

    return render_file_body(list(MemoryStore().list()))


def _print_notes(adapter: HostAdapter | FileHostAdapter) -> None:
    for note in adapter.post_install_notes():
        console.print(f"   [yellow]![/yellow] {escape(note)}")


@app.command("install")
def install(
    host: str | None = typer.Option(
        None, "--host", help="연결할 에이전트(claude·codex·kiro). 생략 시 감지된 전체."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="설명·확인 없이 바로 설치."),
) -> None:
    """기억 주입·사용 로깅을 건다(훅 호스트) 또는 기억 스냅샷을 심는다(파일 호스트)."""
    hooks, files = _resolve_targets(host)
    if not hooks and not files:
        console.print("연결할 에이전트를 찾지 못했습니다.")
        console.print(f"[cyan]--host[/cyan] 로 직접 지정할 수 있습니다: {', '.join(all_names())}")
        return

    if not yes:
        console.print(_EXPLAIN)
        names = ", ".join(a.display_name for a in (*hooks, *files))
        if not typer.confirm(f"연결 대상: {names}\n진행할까요?", default=True):
            console.print("취소했습니다.")
            raise typer.Exit()

    for adapter in hooks:
        _install_hook(adapter)
    if files:
        body = _global_memory_body()
        for file_adapter in files:
            _install_file(file_adapter, body)


def _resolve_targets(
    host: str | None,
) -> tuple[list[HostAdapter], list[FileHostAdapter]]:
    """`--host`를 (훅 대상, 파일 대상)으로 푼다.

    지정하면 그 하나(종류에 맞게), 모르는 이름이면 종료. 안 하면 탐지된 전체.
    """
    if host is None:
        return list(detect_hook_installed()), list(detect_file_supported())
    hook = get_hook_adapter(host)
    if hook is not None:
        return [hook], []
    file = get_file_adapter(host)
    if file is not None:
        return [], [file]
    console.print(f"[red]모르는 호스트:[/red] {host}  (가능: {', '.join(all_names())})")
    raise typer.Exit(code=1)


def _install_hook(adapter: HostAdapter) -> None:
    """훅 호스트에 두 배선(기억 주입 + 사용 로깅)을 건다. 이미 완료면 조용히 표시."""
    path = adapter.config_path()
    config = adapter.load(path)
    if adapter.is_memory_installed(config) and adapter.is_usage_installed(config):
        console.print(f"[green]✓[/green] {adapter.display_name}: 이미 연결돼 있습니다.")
        return
    updated = adapter.with_usage_installed(adapter.with_memory_installed(config))
    backup = adapter.write(path, updated)
    console.print(f"[green]✓[/green] {adapter.display_name} 연결 완료 → {path}")
    if backup:
        console.print(f"   백업: {backup}")
    _print_notes(adapter)


def _install_file(adapter: FileHostAdapter, body: str) -> None:
    """파일 호스트에 기억 스냅샷을 심는다(이미 있으면 최신으로 다시 씀)."""
    path = adapter.content_path()
    already = adapter.is_linked()
    backup = adapter.link(body)
    verb = "갱신" if already else "연결"
    console.print(f"[green]✓[/green] {adapter.display_name} {verb} 완료 → {path}")
    if backup:
        console.print(f"   백업: {backup}")
    if not already:
        _print_notes(adapter)


@app.command("uninstall")
def uninstall(
    host: str | None = typer.Option(
        None, "--host", help="해제할 에이전트(claude·codex·kiro). 생략 시 감지된 전체."
    ),
) -> None:
    """추가했던 연결(훅 배선 또는 스냅샷 파일)을 제거한다."""
    hooks, files = _resolve_targets(host)
    if not hooks and not files:
        console.print("연결된 에이전트를 찾지 못했습니다.")
        return
    for adapter in hooks:
        _uninstall_hook(adapter)
    for file_adapter in files:
        _uninstall_file(file_adapter)


def _uninstall_hook(adapter: HostAdapter) -> None:
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


def _uninstall_file(adapter: FileHostAdapter) -> None:
    if not adapter.is_linked():
        console.print(f"[dim]○[/dim] {adapter.display_name}: 연결돼 있지 않습니다.")
        return
    adapter.unlink()
    console.print(f"[green]✓[/green] {adapter.display_name} 연결 해제 완료 → {adapter.content_path()}")


@app.command("status")
def status() -> None:
    """호스트별 연결 상태를 보여준다(훅은 두 축, 파일은 연결 여부)."""
    for adapter in hook_adapters():
        config = adapter.load(adapter.config_path())
        mem = _dot(adapter.is_memory_installed(config))
        usage = _dot(adapter.is_usage_installed(config))
        console.print(f"[bold]{adapter.display_name}[/bold]  기억 주입: {mem}   사용 로깅: {usage}")
    for file_adapter in file_adapters():
        linked = _dot(file_adapter.is_linked())
        console.print(f"[bold]{file_adapter.display_name}[/bold]  기억 파일: {linked}   [dim](사용 로깅 없음)[/dim]")
    console.print("[cyan]pouch hook install[/cyan] 로 감지된 에이전트에 연결하세요.")


def _dot(installed: bool) -> str:
    return "[green]●[/green] 연결됨" if installed else "[dim]○[/dim] 안 됨"
