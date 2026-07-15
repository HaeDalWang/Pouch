"""`pouch memory` 서브커맨드 — 에이전트가 한 줄로 호출하는 비대화형 인터페이스."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from pouch import paths
from pouch.hooks.settings import (
    is_native_memory_disabled,
    load_settings,
    with_native_memory_disabled,
    write_settings,
)
from pouch.memory.adopt import (
    AdoptionItem,
    SkippedNative,
    partition_existing,
    plan_native_file,
)
from pouch.memory.context import render_session_context
from pouch.memory.liveness import check_reference_alive
from pouch.memory.model import (
    Direction,
    MemoryEntry,
    MemoryScope,
    MemoryState,
    MemoryType,
)
from pouch.memory.pending import is_low_friction
from pouch.memory.recall import recall as recall_fn
from pouch.memory.recall import touch_recalled
from pouch.memory.store import MemoryStore

app = typer.Typer(
    help="🧠 메모리 — 쓸수록 쌓이는 개인 기억.",
    no_args_is_help=True,
)
console = Console()


def _store() -> MemoryStore:
    return MemoryStore()


@app.command("add")
def add(
    name: str = typer.Option(..., "--name", "-n", help="메모리 식별자(파일명이 됨)."),
    description: str = typer.Option(..., "--description", "-d", help="한 줄 요약."),
    body: str = typer.Option(..., "--body", "-b", help="기억할 내용 본문."),
    mem_type: MemoryType = typer.Option(MemoryType.PROJECT, "--type", "-t", help="기억의 성격."),
    scope: MemoryScope = typer.Option(MemoryScope.PROJECT, "--scope", "-s", help="적용 범위."),
    pending: bool = typer.Option(
        False, "--pending", help="확인 전 스테이징(저마찰 타입만: project·reference)."
    ),
    direction: Direction | None = typer.Option(
        None, "--direction", help="boundary 방향(allow/ask/deny). boundary 타입에만."
    ),
) -> None:
    """새 기억을 담는다(같은 이름은 덮어씀).

    --pending은 project·reference에만 허용된다 — feedback·boundary·user는
    오독한 지적이 매 세션 주입되는 standing rule로 굳는 위험이 있어 확인 없이
    스테이징하는 우회를 코드로 막는다(들어오는 문의 타입별 마찰).

    --direction은 boundary에만 의미 있다. CLI로 담는 boundary의 출처는 항상
    사람(user)이다 — vendored 출처는 도구 설치 경로만 새길 수 있어(참칭 불가),
    여기서 source 플래그를 노출하지 않는다.
    """
    if pending and not is_low_friction(mem_type):
        console.print(
            f"[red]✗[/red] '{mem_type.value}'는 확인 없이 스테이징할 수 없습니다 — "
            "--pending 없이 바로 담거나, 사용자 확인을 받으세요."
        )
        raise typer.Exit(code=1)

    if direction is not None and mem_type is not MemoryType.BOUNDARY:
        console.print(
            f"[red]✗[/red] --direction은 boundary 타입에만 붙습니다 "
            f"('{mem_type.value}'에는 방향 개념이 없습니다)."
        )
        raise typer.Exit(code=1)

    entry = MemoryEntry(
        name=name,
        description=description,
        body=body,
        type=mem_type,
        scope=scope,
        state=MemoryState.PENDING if pending else MemoryState.INDEXED,
        direction=direction,
    )
    try:
        path = _store().save(entry)
    except ValueError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]✓[/green] 저장: [bold]{name}[/bold] → {path}")


@app.command("list")
def list_memories() -> None:
    """담긴 기억을 스코프별로 보여준다."""
    entries = list(_store().list())
    if not entries:
        console.print("비어있는 주머니입니다. [cyan]pouch memory add[/cyan] 로 첫 기억을 담아보세요.")
        return
    for scope in (MemoryScope.GLOBAL, MemoryScope.PROJECT):
        scoped = sorted(
            (entry for entry in entries if entry.scope is scope),
            key=lambda entry: entry.name,
        )
        if not scoped:
            continue
        console.print(f"\n[bold]{scope.value}[/bold]")
        for entry in scoped:
            console.print(f"  • [cyan]{entry.name}[/cyan] ({entry.type.value}) — {entry.description}")


@app.command("recall")
def recall_memories(
    query: str = typer.Argument(..., help="검색어(키워드)."),
    limit: int = typer.Option(5, "--limit", "-l", help="최대 결과 수."),
) -> None:
    """기억을 키워드로 회상한다.

    recall 이벤트가 last_recalled를 갱신하고(구조 슬롯 v0 로직), reference
    타입이면 그 자리에서 생존성을 확인한다. 죽었으면 인라인 경고만 한다 —
    강등은 evolve의 위생 제안을 통해서만(제안만 원칙, 자동 없음).
    """
    store = _store()
    hits = recall_fn(store.list(), query, limit=limit)
    if not hits:
        console.print(f"'{query}' 에 맞는 기억이 없습니다.")
        return

    for entry, touched in zip(hits, touch_recalled(hits, now=date.today())):
        store.save(touched)
        console.print(f"• [cyan]{entry.name}[/cyan] ({entry.scope.value}) — {entry.description}")
        if entry.type is MemoryType.REFERENCE and not check_reference_alive(entry):
            console.print(
                f"   [yellow]⚑[/yellow] 가리키는 자원이 사라진 것 같습니다 — "
                "[cyan]pouch evolve[/cyan]로 확인하세요"
            )


@app.command("forget")
def forget_memory(
    name: str = typer.Argument(..., help="삭제할 메모리 이름."),
    scope: MemoryScope | None = typer.Option(
        None, "--scope", "-s", help="스코프(미지정 시 글로벌·프로젝트 모두 탐색)."
    ),
) -> None:
    """기억을 지운다."""
    store = _store()
    scopes = [scope] if scope is not None else [MemoryScope.GLOBAL, MemoryScope.PROJECT]
    removed_any = False
    for target in scopes:
        if store.forget(name, target):
            console.print(f"[green]✓[/green] 삭제: {name} ({target.value})")
            removed_any = True
    if not removed_any:
        console.print(f"'{name}' 기억을 찾지 못했습니다.")
        raise typer.Exit(code=1)


@app.command("promote")
def promote(
    name: str = typer.Argument(..., help="확인하고 인덱스에 올릴 pending 메모리 이름."),
    scope: MemoryScope | None = typer.Option(
        None, "--scope", "-s", help="스코프(미지정 시 글로벌·프로젝트 모두 탐색)."
    ),
) -> None:
    """pending 스테이징을 확인하고 인덱스(INDEXED)로 올린다."""
    store = _store()
    scopes = [scope] if scope is not None else [MemoryScope.GLOBAL, MemoryScope.PROJECT]
    for target in scopes:
        entry = store.get(name, target)
        if entry is not None:
            store.promote(entry)
            console.print(f"[green]✓[/green] 확인: [bold]{name}[/bold] → 인덱스에 올림")
            return
    console.print(f"'{name}' 기억을 찾지 못했습니다.")
    raise typer.Exit(code=1)


def gather_adoption(
    project_root: Path,
) -> tuple[Path, list[AdoptionItem], list[SkippedNative]]:
    """네이티브를 훑어 이관 계획을 낸다(저장은 안 함). native_dir·이관목록·건너뜀 반환.

    덮어쓰기 방지(partition_existing)까지 적용해서, 반환하는 items는 실제로 저장할 것만.
    native_dir가 없으면 빈 리스트로 돌려준다(호출부가 판단). 파일 읽기만 하고 쓰기는
    안 한다 — CLI(`adopt`)와 init 마법사가 같은 계획 로직을 공유한다.
    """
    native_dir = paths.claude_project_memory_dir(project_root)
    if not native_dir.is_dir():
        return native_dir, [], []

    items: list[AdoptionItem] = []
    skipped: list[SkippedNative] = []
    for path in sorted(p for p in native_dir.glob("*.md") if p.name != "MEMORY.md"):
        created = date.fromtimestamp(path.stat().st_mtime)
        result = plan_native_file(
            path.read_text(encoding="utf-8"),
            source_path=str(path),
            stem=path.stem,
            created=created,
        )
        if isinstance(result, AdoptionItem):
            items.append(result)
        else:
            skipped.append(result)

    existing = {
        (e.name, e.scope)
        for e in MemoryStore(project_dir=project_root / ".pouch" / "memory").list()
    }
    items, existing_skips = partition_existing(items, existing=existing)
    return native_dir, items, skipped + existing_skips


def apply_adoption(
    project_root: Path, items: list[AdoptionItem], *, disable_native: bool
) -> Path | None:
    """이관 계획을 저장하고(save_many), 옵션대로 네이티브 자동로드를 끈다. .bak 경로 반환."""
    MemoryStore(project_dir=project_root / ".pouch" / "memory").save_many(
        item.entry for item in items
    )
    if not disable_native:
        return None
    settings_path = paths.claude_settings_path()
    settings = load_settings(settings_path)
    if is_native_memory_disabled(settings):
        return None
    return write_settings(settings_path, with_native_memory_disabled(settings))


def _print_adoption_plan(
    project_root: Path,
    native_dir: Path,
    items: list[AdoptionItem],
    skipped: list[SkippedNative],
    *,
    disable_native: bool,
) -> None:
    """이관 계획을 한 화면으로 그린다(dry-run·적용 공통 머리)."""
    console.print(f"🦦 memory adopt — 프로젝트: [bold]{project_root.name}[/bold]")
    console.print(f"   네이티브: {native_dir}")
    console.print(f"   발견 {len(items) + len(skipped)}건 (이관 {len(items)} · 건너뜀 {len(skipped)})")

    indexed = [i for i in items if i.entry.state is MemoryState.INDEXED]
    pending = [i for i in items if i.entry.state is MemoryState.PENDING]
    archived = [i for i in items if i.entry.state is MemoryState.ARCHIVED]

    if indexed:
        console.print(f"\n[bold]주입됨 INDEXED[/bold] {len(indexed)}건 — 안정 핵심")
        for item in indexed:
            e = item.entry
            console.print(f"  • [cyan]{e.name}[/cyan] ({e.type.value}) [{e.scope.value}]")
    if pending:
        console.print(f"\n[bold]리뷰 대기 PENDING[/bold] {len(pending)}건 — 주입 안 함·recall 가능")
        for item in pending:
            e = item.entry
            console.print(f"  • [cyan]{e.name}[/cyan] ({e.type.value}) [{e.scope.value}]")
    if archived:
        console.print(
            f"\n[bold]보관 ARCHIVED[/bold] {len(archived)}건 — 날짜 박힌 세션로그(주입 X·recall O)"
        )
        for item in archived:
            e = item.entry
            console.print(f"  • [cyan]{e.name}[/cyan] ({e.type.value}) [{e.scope.value}]")
    if skipped:
        console.print(f"\n[bold]건너뜀[/bold] {len(skipped)}건")
        for s in skipped:
            console.print(f"  • {Path(s.source_path).name} — [dim]{s.reason}[/dim]")

    native_state = (
        "끔 (autoMemoryEnabled=false · 대체 확정)"
        if disable_native
        else "유지 (안전망) — 완전 대체는 --disable-native"
    )
    console.print(f"\n  네이티브 자동로드: [yellow]{native_state}[/yellow]")


@app.command("adopt")
def adopt(
    from_path: Path | None = typer.Option(
        None,
        "--from",
        help="이관할 프로젝트 경로(기본: 현재 프로젝트). Claude를 서브디렉토리에서 돌렸으면 그 경로를 준다.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="무엇이 어디로·어떤 계층으로 갈지 미리보기만(아무것도 안 바꿈)."
    ),
    disable_native: bool = typer.Option(
        False,
        "--disable-native/--no-disable-native",
        help="이관 후 네이티브 자동로드까지 끈다(대체 확정). 기본은 옮기기만 — 네이티브는 안전망으로 남긴다.",
    ),
) -> None:
    """Claude 네이티브 메모리를 pouch로 이관한다(대체 A안 §2). 원본은 안 지운다(복사).

    타입이 자리와 계층을 정한다: user·feedback→global 주입, reference→project 주입,
    project→project 리뷰 대기(주입 안 함). 네이티브가 어긴 "안정 핵심만 주입"을 복원한다.
    시계(mtime→created)는 이 경계에서만 읽는다.
    """
    project_root = from_path.resolve() if from_path else (paths.find_project_root() or Path.cwd())
    # gather_adoption이 계획 계산 + 덮어쓰기 방지(partition_existing)까지 한다("떨어진다 ≠
    # 삭제된다"). 계획 단계에서 걸러야 dry-run에도 "이미 있음"이 보이고, 재실행·배치 내
    # 충돌이 예방된다. init 마법사도 같은 함수를 공유한다.
    native_dir, items, skipped = gather_adoption(project_root)
    if not native_dir.is_dir():
        console.print(f"네이티브 메모리가 없습니다: {native_dir}")
        raise typer.Exit()
    if not items and not skipped:
        console.print(f"이관할 네이티브 메모리가 없습니다: {native_dir}")
        raise typer.Exit()

    _print_adoption_plan(project_root, native_dir, items, skipped, disable_native=disable_native)

    if dry_run:
        console.print("\n적용하려면 [cyan]--dry-run[/cyan] 없이 다시 실행하세요.")
        return

    backup = apply_adoption(project_root, items, disable_native=disable_native)
    injected = sum(1 for i in items if i.entry.state is MemoryState.INDEXED)
    pending = sum(1 for i in items if i.entry.state is MemoryState.PENDING)
    console.print(
        f"\n[green]✓[/green] 이관 {len(items)}건 "
        f"(주입 {injected} · 리뷰 대기 {pending} · 보관 {len(items) - injected - pending})"
    )
    if disable_native:
        console.print("[green]✓[/green] 네이티브 자동로드 끔 (autoMemoryEnabled=false)")
        if backup:
            console.print(f"   백업: {backup}")
    console.print(
        "   리뷰 대기 확인: [cyan]pouch memory list[/cyan] · "
        "올리기: [cyan]pouch memory promote <이름>[/cyan]"
    )


@app.command("context")
def context() -> None:
    """SessionStart hook용: 세션 통로를 평문으로 출력한다(에이전트 주입용).

    고정 구역(boundary+기억 인덱스) 위, 쪽지 구역(먼저 내미는 제안) 아래.
    쪽지는 격리된 note_zone에서 조립되므로, 조립이 터져도 고정 구역은 그대로
    나간다(render_session_context의 비대칭 격리). 시계는 이 경계에서만 읽는다.
    """
    from datetime import datetime

    from pouch.checkpoint.anchor import load_anchor
    from pouch.evolution.session_nudge import build_session_note, gather_nudge_summary

    now = datetime.now().isoformat(timespec="seconds")

    def _note_zone() -> str:
        return build_session_note(gather_nudge_summary(now=now), now=now)

    text = render_session_context(
        _store().list(), anchor=load_anchor(), note_zone=_note_zone
    )
    if text:
        typer.echo(text, nl=False)
