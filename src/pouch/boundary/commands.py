"""`pouch boundary` — 자율성 경계의 1급 명령 표면(add/list/remove).

경계는 memory(MemoryType.BOUNDARY)로 저장되지만, `pouch memory add -t boundary`의
곁다리로 묻혀 있던 것을 자기 동사로 꺼낸다. 세 구멍을 메운다: 짓는 입구(add,
--direction 필수) · 한눈에 보기(list, 스코프·방향별) · 지우기(remove). 저장 모델도
비강제 철학도 안 건드린다 — CLI 표면만 승격(BOUNDARY-PROMOTION.md 옵션 A).
"""

from __future__ import annotations

import typer
from rich.console import Console

from pouch.memory.model import (
    SOURCE_USER,
    Direction,
    MemoryEntry,
    MemoryScope,
    MemoryState,
    MemoryType,
)
from pouch.memory.store import MemoryStore

app = typer.Typer(
    help="🚧 경계 — 자율성의 허용·확인·금지(맨 위에 주입되는 규칙).",
    no_args_is_help=True,
)
console = Console()

# 방향별 색 — deny는 붉게(가장 강함), ask는 노랗게, allow는 초록. 라벨의 무게를 눈에 싣는다.
_DIR_COLOR = {Direction.DENY: "red", Direction.ASK: "yellow", Direction.ALLOW: "green"}


def _dir_color(direction: Direction | None) -> str:
    return _DIR_COLOR.get(direction, "dim") if direction else "dim"


@app.command("add")
def add(
    name: str = typer.Option(..., "--name", "-n", help="경계 식별자(파일명이 됨)."),
    description: str = typer.Option(..., "--description", "-d", help="한 줄 요약."),
    direction: Direction = typer.Option(
        ..., "--direction", help="방향(allow/ask/deny) — 필수. 방향 없는 경계의 애매함을 입구에서 막는다."
    ),
    body: str = typer.Option("", "--body", "-b", help="경계 본문(맨 위에 함께 주입됨). 선택."),
    scope: MemoryScope = typer.Option(
        MemoryScope.PROJECT, "--scope", "-s", help="적용 범위(허용은 프로젝트로 좁혀 누수 방지)."
    ),
) -> None:
    """자율성 경계를 건다 — 세션 맨 위에 주입되는 허용/확인/금지 규칙.

    방향은 필수다: allow(자율로 해라)·ask(하기 전 물어라)·deny(하지 마라). 출처는
    언제나 사람(user)이다 — 도구가 딸고 오는 vendored 경계는 도구 설치 경로만 새길 수
    있어(참칭 불가), 여기선 출처를 노출하지 않는다.

    pouch는 경계를 강제하지 않는다(차단기 안 닮) — 에이전트가 알고 존중하게 하는 층이다.
    """
    entry = MemoryEntry(
        name=name,
        description=description,
        body=body,
        type=MemoryType.BOUNDARY,
        scope=scope,
        direction=direction,
        state=MemoryState.INDEXED,  # 경계는 항상 인덱스(pending 우회 없음 — 곧장 주입).
    )
    try:
        path = MemoryStore().save(entry)
    except ValueError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc
    label = direction.value.upper()
    console.print(
        f"[green]✓[/green] 경계 [[{_dir_color(direction)}]{label}[/]] "
        f"[bold]{name}[/bold] ({scope.value}) → {path}"
    )


@app.command("list")
def list_boundaries() -> None:
    """건 경계를 스코프·방향별로 한 화면에 — "여기서 내 자율 범위는?".

    주입 중인(indexed) 경계만 보인다 — 강등된(archived) 경계는 더 이상 효력이 없어
    "지금 내 범위"에서 뺀다. 출처를 함께 보여준다: 🔒 내가 건 것 / 📦 도구가 딸고 온 것.
    """
    boundaries = [
        m
        for m in MemoryStore().list()
        if m.type is MemoryType.BOUNDARY and m.state is MemoryState.INDEXED
    ]
    if not boundaries:
        console.print("건 경계가 없습니다. [cyan]pouch boundary add[/cyan] 로 첫 경계를 거세요.")
        return

    for scope in (MemoryScope.GLOBAL, MemoryScope.PROJECT):
        scoped = sorted((b for b in boundaries if b.scope is scope), key=lambda b: b.name)
        if not scoped:
            continue
        console.print(f"\n[bold]{scope.value}[/bold]")
        for b in scoped:
            label = f"[{b.direction.value.upper()}]" if b.direction else "[?]"
            origin = "🔒" if b.source == SOURCE_USER else "📦"
            console.print(
                f"  {origin} [[{_dir_color(b.direction)}]{label[1:-1]}[/]] "
                f"[cyan]{b.name}[/cyan] — {b.description}"
            )


@app.command("remove")
def remove(
    name: str = typer.Argument(..., help="지울 경계 이름."),
    scope: MemoryScope | None = typer.Option(
        None, "--scope", "-s", help="스코프(미지정 시 글로벌·프로젝트 모두 탐색)."
    ),
) -> None:
    """경계를 지운다. 같은 이름의 일반 기억은 건드리지 않는다(경계만 지움)."""
    store = MemoryStore()
    scopes = [scope] if scope is not None else [MemoryScope.GLOBAL, MemoryScope.PROJECT]
    for target in scopes:
        entry = store.get(name, target)
        if entry is not None and entry.type is MemoryType.BOUNDARY:
            store.forget(name, target)
            console.print(f"[green]✓[/green] 경계 삭제: {name} ({target.value})")
            return
    console.print(f"'{name}' 경계를 찾지 못했습니다.")
    raise typer.Exit(code=1)
