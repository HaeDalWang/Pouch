"""`pouch catalog` 서브커맨드 — 공급 고리: 주머니에 담을 수 있는 것을 등록한다.

Phase 3의 importer·install·sync는 전부 있었는데 CLI 배선이 없어서, end user
경로로는 주머니를 채울 방법이 없었다(빈 카탈로그 위에서 전 루프 공회전).
여기가 그 입구다. install은 drop 후 재부착의 공식 입구이기도 하다.

경로 판별(classify_source)은 순수 함수로 분리해 단위 테스트하고,
시계·파일 IO는 CLI 경계에서만 다룬다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from pouch import paths
from pouch.catalog.importer import (
    PluginImportResult,
    import_mcp_servers,
    import_owned_skill,
    import_plugin,
    import_vendored_skill,
)
from pouch.catalog.install import install_entry
from pouch.catalog.store import CatalogStore
from pouch.catalog.sync import sync_all
from pouch.evolution.state import active_entries

app = typer.Typer(
    help="📦 catalog — 주머니에 담을 수 있는 것의 레지스트리.",
    no_args_is_help=True,
)
console = Console()

_SKILL_FILENAME = "SKILL.md"
_MCP_FILENAME = ".mcp.json"


def _now() -> str:
    """현재 시각 ISO8601. 시계는 CLI 경계에서만 읽는다."""
    return datetime.now().isoformat(timespec="seconds")


def classify_source(path: Path) -> str:
    """import 대상을 경로만 보고 판별한다: plugin / skill / mcp.

    plugin(번들)이 skill보다 우선이다 — skills/를 품은 디렉토리는 분해 대상.
    판별 불가면 ValueError로 명확히 실패한다(조용히 삼키지 않음).
    """
    if path.is_dir():
        if (path / _MCP_FILENAME).exists() or (path / "skills").is_dir():
            return "plugin"
        if (path / _SKILL_FILENAME).exists():
            return "skill"
        raise ValueError(f"'{path}'에서 plugin/skill/mcp 어느 것도 찾지 못했습니다.")
    if path.name == _MCP_FILENAME:
        return "mcp"
    if path.name == _SKILL_FILENAME:
        return "skill"
    raise ValueError(f"'{path}'는 import할 수 있는 형태가 아닙니다 (SKILL.md / .mcp.json / plugin 디렉토리).")


def _resolve_skill_path(path: Path) -> Path:
    """skill 대상이 디렉토리면 안의 SKILL.md로 내려간다."""
    return path / _SKILL_FILENAME if path.is_dir() else path


_DISCOVER_MAX_DEPTH = 3  # marketplace 캐시가 <mkt>/<plugin>/<version>/ 3단


def find_plugin_roots(path: Path, *, max_depth: int = _DISCOVER_MAX_DEPTH) -> list[Path]:
    """중첩된 plugin 루트를 찾는다 — marketplace 캐시 구조 대응.

    실측(2026-07-02): `~/.claude/plugins/cache`는 <marketplace>/<plugin>/<version>/
    구조라 최상위를 가리키면 classify가 실패한다. 숨김 디렉토리(.claude 등 번들
    사본)는 건너뛰고, 루트를 찾으면 그 안으로는 더 내려가지 않는다(중복 방지).
    """

    def _is_root(directory: Path) -> bool:
        return (directory / _MCP_FILENAME).exists() or (directory / "skills").is_dir()

    roots: list[Path] = []
    frontier = [path]
    for _ in range(max_depth):
        next_frontier: list[Path] = []
        for parent in frontier:
            for child in sorted(parent.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                if _is_root(child):
                    roots.append(child)
                else:
                    next_frontier.append(child)
        frontier = next_frontier
    return roots


def _classify_or_discover(path: Path) -> tuple[str, Path]:
    """직접 판별하고, 안 되면 한 겹 안쪽에서 plugin 루트를 찾아본다.

    여러 개가 보이면 자동으로 다 들이지 않는다 — 어떤 주머니를 찰지는
    사용자가 고른다(제안만 원칙).
    """
    try:
        return classify_source(path), path
    except ValueError:
        if not path.is_dir():
            raise
        roots = find_plugin_roots(path)
        if not roots:
            raise
        if len(roots) > 1:
            listing = "\n".join(f"  • {root}" for root in roots)
            raise ValueError(
                f"plugin이 여러 개 보입니다. 하나를 골라 다시 실행하세요:\n{listing}"
            ) from None
        console.print(f"[dim]↳ 안쪽에서 plugin을 찾았습니다: {roots[0]}[/dim]")
        return "plugin", roots[0]


@app.command("import")
def import_source(
    source_path: Path = typer.Argument(..., help="SKILL.md / .mcp.json / plugin 디렉토리."),
    own: bool = typer.Option(False, "--own", help="owned로 입양(본문 소유, upstream 끊음)."),
    force: bool = typer.Option(False, "--force", help="owned 재입양 시 내 본문을 덮는 것을 허용."),
    source: str = typer.Option("local", "--source", help="출처 라벨."),
    tag: list[str] = typer.Option([], "--tag", help="붙일 태그(반복 가능)."),
) -> None:
    """주머니에 담을 수 있도록 카탈로그에 등록한다(설치는 install이 함)."""
    path = source_path.expanduser().resolve()
    if not path.exists():
        console.print(f"[red]✗[/red] 경로가 없습니다: {path}")
        raise typer.Exit(code=1)

    store = CatalogStore()
    tags = tuple(tag)
    try:
        kind, path = _classify_or_discover(path)
        result = _run_import(kind, path, store, own=own, force=force, source=source, tags=tags)
    except (ValueError, FileExistsError) as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc

    for skip in result.skipped:
        console.print(f"[yellow]![/yellow] 건너뜀: {skip.reason}")
    console.print(f"[green]✓[/green] {len(result.entries)}개 항목을 카탈로그에 담았습니다:")
    for entry in result.entries:
        console.print(f"  • [cyan]{entry.id}[/cyan] ({entry.ownership.value})")
    console.print("   설치: [cyan]pouch catalog install <id>[/cyan]")


def _run_import(
    kind: str,
    path: Path,
    store: CatalogStore,
    *,
    own: bool,
    force: bool,
    source: str,
    tags: tuple[str, ...],
) -> PluginImportResult:
    """판별된 종류에 맞는 importer로 위임한다.

    plugin은 깨진 조각을 건너뛰며 리포트로 돌아오고, 단일 대상(skill/mcp)은
    건너뛸 나머지가 없으니 실패를 그대로 올린다(호출부가 사람 말로 보고).
    """
    if kind == "plugin":
        return import_plugin(path, store, synced_at=_now(), source=source, tags=tags)
    if kind == "mcp":
        servers = import_mcp_servers(path, store, source=source, tags=tags)
        return PluginImportResult(entries=tuple(servers))
    skill_path = _resolve_skill_path(path)
    if own:
        entry = import_owned_skill(skill_path, store, source=source, tags=tags, force=force)
    else:
        entry = import_vendored_skill(
            skill_path, store, upstream=str(skill_path), synced_at=_now(),
            source=source, tags=tags,
        )
    return PluginImportResult(entries=(entry,))


@app.command("list")
def list_entries() -> None:
    """카탈로그 항목과 표면 상태(설치 여부)를 보여준다."""
    entries = list(CatalogStore().list())
    if not entries:
        console.print("📦 카탈로그가 비어 있습니다.")
        console.print("   담기: [cyan]pouch catalog import <경로>[/cyan]")
        return

    active = active_entries()
    console.print(f"📦 [bold]카탈로그[/bold] ({len(entries)}개)\n")
    for entry in entries:
        surface = "[green]●[/green] 표면" if entry.id in active else "[dim]○[/dim]"
        tags = f" [dim]{', '.join(entry.tags)}[/dim]" if entry.tags else ""
        console.print(f"  {surface} [cyan]{entry.id}[/cyan] ({entry.ownership.value}){tags}")


@app.command("install")
def install(
    entry_id: str = typer.Argument(..., help="설치할 카탈로그 항목 id."),
    skills_dir: Path = typer.Option(
        None, "--skills-dir", help="스킬 설치 위치(기본: Claude skills)."
    ),
    mcp_config: Path = typer.Option(
        None, "--mcp-config", help=".mcp.json 위치(기본: 현재 프로젝트)."
    ),
) -> None:
    """항목을 활성 표면에 올린다 — drop된 도구의 재부착도 이 명령이다."""
    entry = CatalogStore().get(entry_id)
    if entry is None:
        console.print(f"[red]✗[/red] 카탈로그에 '{entry_id}'가 없습니다. [cyan]pouch catalog list[/cyan]로 확인하세요.")
        raise typer.Exit(code=1)

    try:
        result = install_entry(
            entry,
            skills_dir=skills_dir or paths.claude_skills_dir(),
            mcp_config_path=mcp_config or paths.project_mcp_config_path(),
        )
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]✓[/green] [cyan]{entry_id}[/cyan]를 표면에 올렸습니다 → {result}")


@app.command("sync")
def sync() -> None:
    """vendored 항목의 upstream을 재방문해 갱신한다(개인화 overlay는 보존)."""
    try:
        synced = sync_all(CatalogStore(), synced_at=_now())
    except FileNotFoundError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not synced:
        console.print("📦 sync할 vendored 항목이 없습니다.")
        return
    console.print(f"[green]✓[/green] {len(synced)}개 항목을 upstream과 맞췄습니다.")
