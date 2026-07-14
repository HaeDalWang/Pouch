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
    import_hooks,
    import_mcp_servers,
    import_owned_skill,
    import_plugin,
    import_vendored_skill,
)
from pouch.catalog.boundary import recommended_boundary_memories
from pouch.catalog.install import install_entry
from pouch.catalog.model import SURFACE_PLUGIN, ToolEntry, ToolKind
from pouch.catalog.promote import promote
from pouch.catalog.store import CatalogStore
from pouch.memory.store import MemoryStore
from pouch.catalog.sync import SyncReport, moved_component, sync_all
from pouch.backup.local import backup_to_local
from pouch.evolution.orchestrate import migrate as migrate_unused
from pouch.evolution.orchestrate import plan_migrate
from pouch.evolution.state import active_entries

app = typer.Typer(
    help="📦 catalog — 주머니에 담을 수 있는 것의 레지스트리.",
    no_args_is_help=True,
)
console = Console()

_SKILL_FILENAME = "SKILL.md"
_MCP_FILENAME = ".mcp.json"
_HOOKS_FILENAME = "hooks.json"


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
    if path.name == _HOOKS_FILENAME:
        return "hooks"
    raise ValueError(
        f"'{path}'는 import할 수 있는 형태가 아닙니다 "
        "(SKILL.md / .mcp.json / hooks.json / plugin 디렉토리)."
    )


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

    # 관문 (다): import는 소스 스테이징에만 담는다 — 카탈로그 진입 0개.
    # 사용자가 실제로 쓰거나(evolve의 reconcile) install/세트로 명시하면 그때
    # 카탈로그로 진입한다. 여기서 전량 자동 등록만 끊는다("판단"이 아니라).
    store = CatalogStore(catalog_dir=paths.sources_dir())
    tags = tuple(tag)
    try:
        kind, path = _classify_or_discover(path)
        result = _run_import(kind, path, store, own=own, force=force, source=source, tags=tags)
    except (ValueError, FileExistsError) as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc

    for skip in result.skipped:
        console.print(f"[yellow]![/yellow] 건너뜀: {skip.reason}")
    console.print(
        f"[green]✓[/green] {len(result.entries)}개 항목을 소스로 담았습니다 "
        "[dim](쓰거나 install하면 카탈로그로 진입)[/dim]:"
    )
    for entry in result.entries:
        console.print(f"  • [cyan]{entry.id}[/cyan] ({entry.ownership.value})")
    console.print("   지금 올리기: [cyan]pouch catalog install <id>[/cyan]")


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
    if kind == "hooks":
        hooks = import_hooks(path, store, source=source, tags=tags)
        return PluginImportResult(entries=tuple(hooks))
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
def list_entries(
    sources: bool = typer.Option(
        False, "--sources", help="진입 전 소스 스테이징에 재워둔 것을 보여준다."
    ),
) -> None:
    """카탈로그 항목과 표면 상태(설치 여부)를 보여준다.

    --sources는 관문 (다)의 "가리키기" 칸을 연다: import했지만 아직 안 써서
    카탈로그에 진입하지 않은 것들(백과사전에 있으나 노트엔 없는 페이지).
    """
    if sources:
        _list_sources()
        return

    entries = list(CatalogStore().list())
    if not entries:
        staged = list(CatalogStore(catalog_dir=paths.sources_dir()).list())
        console.print("📦 카탈로그가 비어 있습니다.")
        if staged:
            console.print(
                f"   소스에 {len(staged)}개가 재워져 있어요 — 쓰거나 install하면 진입합니다."
            )
            console.print("   보기: [cyan]pouch catalog list --sources[/cyan]")
        else:
            console.print("   담기: [cyan]pouch catalog import <경로>[/cyan]")
        return

    active = active_entries()
    console.print(f"📦 [bold]카탈로그[/bold] ({len(entries)}개)\n")
    for entry in entries:
        surface = "[green]●[/green] 표면" if entry.id in active else "[dim]○[/dim]"
        tags = f" [dim]{', '.join(entry.tags)}[/dim]" if entry.tags else ""
        console.print(f"  {surface} [cyan]{entry.id}[/cyan] ({entry.ownership.value}){tags}")


def _list_sources() -> None:
    """소스 스테이징 목록 — 진입 전에 재워둔 것(카탈로그 목록엔 안 뜨는 것)."""
    staged = list(CatalogStore(catalog_dir=paths.sources_dir()).list())
    if not staged:
        console.print("📚 소스에 재워둔 것이 없습니다.")
        console.print("   담기: [cyan]pouch catalog import <경로>[/cyan]")
        return
    catalog_ids = {e.id for e in CatalogStore().list()}
    console.print(f"📚 [bold]소스 스테이징[/bold] ({len(staged)}개) [dim]— 쓰면 카탈로그로 진입[/dim]\n")
    for entry in staged:
        entered = "[green]↑ 진입함[/green]" if entry.id in catalog_ids else "[dim]· 대기[/dim]"
        console.print(f"  {entered} [cyan]{entry.id}[/cyan] ({entry.ownership.value})")


def _confirm_hook_install(entry: ToolEntry, *, yes: bool) -> bool:
    """훅 설치 관문 — 실행될 명령 원문을 반드시 보여주고 동의를 받는다.

    훅은 내 컴퓨터에서 명령을 실제로 실행하므로 다른 종류보다 관문이 무겁다.
    --yes면 물음은 건너뛰되 원문 출력은 항상 남긴다(배승도 결정, 2026-07-07).
    """
    recipe = entry.recipe or {}
    where = recipe.get("event", "?")
    if recipe.get("matcher"):
        where += f" ({recipe['matcher']})"
    console.print(f"⚡ 이 훅은 [bold]{where}[/bold] 때마다 아래 명령을 실행합니다:")
    for hook in recipe.get("hooks", []):
        console.print(f"   [yellow]$ {hook.get('command', '')}[/yellow]")
    if yes:
        return True
    return typer.confirm("이 명령이 실행되는 데 동의하나요?", default=False)


@app.command("install")
def install(
    entry_id: str = typer.Argument(..., help="설치할 카탈로그 항목 id."),
    skills_dir: Path = typer.Option(
        None, "--skills-dir", help="스킬 설치 위치(기본: Claude skills)."
    ),
    mcp_config: Path = typer.Option(
        None, "--mcp-config", help=".mcp.json 위치(기본: 현재 프로젝트)."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 없이 설치(훅 명령 출력은 항상 남음)."),
) -> None:
    """항목을 활성 표면에 올린다 — drop된 도구의 재부착도 이 명령이다.

    관문 (다): 명시 install도 진입 트리거다. 카탈로그에 없고 소스에만 있으면
    먼저 promote해 카탈로그로 진입시킨 뒤 표면에 올린다("일부러 골라 올림"은
    실사용과 같은 진입 근거).
    """
    catalog = CatalogStore()
    entry = catalog.get(entry_id)
    if entry is None:
        entry = promote(
            entry_id,
            source_store=CatalogStore(catalog_dir=paths.sources_dir()),
            catalog_store=catalog,
        )
    if entry is None:
        console.print(f"[red]✗[/red] 카탈로그·소스에 '{entry_id}'가 없습니다. [cyan]pouch catalog list[/cyan]로 확인하세요.")
        raise typer.Exit(code=1)
    if entry.surface == SURFACE_PLUGIN:
        console.print(
            f"[red]✗[/red] '{entry_id}'는 플러그인이 표면을 관리합니다 — "
            "pouch가 또 등록하면 중복이 됩니다. 플러그인 설정에서 켜고 끄세요."
        )
        raise typer.Exit(code=1)
    if entry.kind is ToolKind.HOOK and not _confirm_hook_install(entry, yes=yes):
        console.print("설치하지 않았습니다.")
        return

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
    _promote_boundaries(entry)


def _promote_boundaries(entry: ToolEntry) -> None:
    """엔트리가 딸고 온 권장 boundary를 boundary 메모리로 승격한다(설치 후).

    standing rule을 세우는 일이라 심은 것을 투명하게 보고한다. 재부착 안전:
    같은 이름이 이미 있으면 사용자가 손봤을 수 있어 덮지 않고 건너뛴다. project
    스코프인데 프로젝트 루트가 없으면 그 하나만 건너뛰고 경고(설치는 이미 성공).
    """
    from datetime import date

    mems = recommended_boundary_memories(entry, now=date.today())
    if not mems:
        return

    store = MemoryStore()
    for mem in mems:
        if store.get(mem.name, mem.scope) is not None:
            console.print(
                f"  [dim]· 경계 '{mem.name}'는 이미 있어 건드리지 않았습니다.[/dim]"
            )
            continue
        try:
            store.save(mem)
        except ValueError:
            console.print(
                f"  [yellow]⚑[/yellow] 경계 '{mem.name}'는 project 범위인데 "
                "프로젝트 루트가 없어 건너뛰었습니다."
            )
            continue
        console.print(
            f"  [green]+[/green] 권장 경계 심음: [bold]{mem.name}[/bold] "
            f"[{mem.direction.value if mem.direction else '?'}] — {mem.description}"
        )


@app.command("uninstall")
def uninstall(
    entry_id: str = typer.Argument(..., help="표면에서 내릴 카탈로그 항목 id."),
    skills_dir: Path = typer.Option(
        None, "--skills-dir", help="스킬 설치 위치(기본: Claude skills)."
    ),
    mcp_config: Path = typer.Option(
        None, "--mcp-config", help=".mcp.json 위치(기본: 현재 프로젝트)."
    ),
) -> None:
    """항목을 표면에서 손으로 내린다 — 카탈로그·개인화는 남는다.

    evolve가 제안 못 하는 종류(훅처럼 사용 신호가 안 찍히는 것)의 유일한
    내리는 문이기도 하다. 되올리기는 [cyan]catalog install[/cyan] 한 번.
    """
    from pouch.catalog.uninstall import uninstall_entry
    from pouch.evolution.state import mark_dropped

    entry = CatalogStore().get(entry_id)
    if entry is None:
        console.print(f"[red]✗[/red] 카탈로그에 '{entry_id}'가 없습니다.")
        raise typer.Exit(code=1)
    if entry.surface == SURFACE_PLUGIN:
        console.print(
            f"[red]✗[/red] '{entry_id}'는 플러그인이 표면을 관리합니다 — "
            "플러그인 설정에서 켜고 끄세요."
        )
        raise typer.Exit(code=1)

    uninstall_entry(
        entry,
        skills_dir=skills_dir or paths.claude_skills_dir(),
        mcp_config_path=mcp_config or paths.project_mcp_config_path(),
    )
    mark_dropped(entry_id)
    console.print(
        f"[green]✓[/green] [cyan]{entry_id}[/cyan]를 표면에서 내렸습니다"
        " (카탈로그·개인화는 그대로). 되올리기: [cyan]pouch catalog install"
        f" {entry_id}[/cyan]"
    )


@app.command("sync")
def sync() -> None:
    """vendored 항목의 upstream을 재방문해 갱신한다(개인화 overlay는 보존).

    upstream이 버전 이동으로 죽었으면 body는 자동으로 이사시키고,
    boundary가 걸린 이사는 확인 요망을 flag만 한다(막지 않음).
    """
    report = sync_all(CatalogStore(), synced_at=_now())
    if report.is_empty:
        console.print("📦 sync할 vendored 항목이 없습니다.")
        return
    _render_sync_report(report)


def _render_sync_report(report: SyncReport) -> None:
    """이사·유실·boundary flag를 사람 말로 보고한다."""
    if report.synced:
        console.print(f"[green]✓[/green] {len(report.synced)}개 항목을 upstream과 맞췄습니다.")
    for moved in report.rehomed:
        old_ver, new_ver = moved_component(moved.old_upstream, moved.entry.upstream or "")
        console.print(
            f"[green]↪[/green] [cyan]{moved.entry.id}[/cyan] — {old_ver} → {new_ver} 이사"
        )
        if moved.needs_boundary_check:
            boundaries = ", ".join(moved.entry.overlay.boundaries)
            console.print(
                f"   [yellow]⚑[/yellow] boundary({boundaries}) — 새 버전에서 유효성 확인 요망"
            )
    for lost in report.missing:
        console.print(
            f"[yellow]![/yellow] [cyan]{lost.entry_id}[/cyan] — upstream이 증발했습니다"
            "(본체 유실). 카탈로그·개인화는 남아있어요."
            " 재연결: [cyan]pouch catalog import <새 경로>[/cyan]"
        )


@app.command("migrate")
def migrate(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="옮길 목록만 보여주고 아무것도 안 함(볼게, 해 아님)."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 없이 바로 강등."),
) -> None:
    """안 쓰는 카탈로그 도구를 소스 스테이징으로 되돌린다(관문 이전 잉여 정리).

    관문 (다) 이전 import는 실사용과 무관하게 카탈로그에 직행시켰다. 이 일회성
    통로가 그 잉여를 관문 뒤(소스)로 되돌린다 — 실제로 쓴 것만 카탈로그에 남긴다.
    reconcile(진입)과 달리 evolve 자동 루프에 없다: 파괴적(카탈로그 삭제)이라
    사용자가 의도적으로 부르고, 실데이터를 옮기므로 적용 전 자동 백업을 동반한다.
    """
    catalog_store = CatalogStore()
    source_store = CatalogStore(catalog_dir=paths.sources_dir())

    candidates = plan_migrate(catalog_store=catalog_store, source_store=source_store)
    if not candidates:
        console.print("📦 소스로 되돌릴 도구가 없습니다. 카탈로그가 실사용에 맞게 유지되고 있어요.")
        return

    console.print(
        "📦 [bold]안 쓰는 카탈로그 도구[/bold] (소스로 되돌려도 재사용하면 다시 진입합니다)\n"
    )
    for entry_id in candidates:
        console.print(f"  ▽ [cyan]{entry_id}[/cyan] → 소스 스테이징으로")

    if dry_run:
        console.print(
            f"\n{len(candidates)}개가 대상입니다. 실행하려면: [cyan]pouch catalog migrate --yes[/cyan]"
            " [dim](적용 전 자동 백업)[/dim]"
        )
        return

    if not yes and not typer.confirm(
        "\n이 도구들을 소스로 되돌릴까요? (적용 전 백업을 뜹니다)", default=False
    ):
        console.print("그대로 두었습니다.")
        return

    # 이동 전 자동 백업 — 실데이터를 옮기므로 되돌림 경로를 먼저 확보한다.
    archive = backup_to_local(paths.global_root(), paths.backup_dir(), now=_now())
    console.print(f"[green]✓[/green] 적용 전 백업 → {archive}")

    demoted = migrate_unused(source_store=source_store, catalog_store=catalog_store)
    console.print(f"\n[green]✓[/green] {len(demoted)}개를 소스로 되돌렸습니다: {', '.join(demoted)}")
    console.print(
        "   재사용하면 [cyan]pouch evolve[/cyan]가 다시 카탈로그로 진입시킵니다"
        f" · 되돌리려면 [cyan]pouch restore {archive}[/cyan]"
    )
