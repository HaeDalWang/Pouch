"""`pouch init` — 환경을 감지하고 나에게 맞춰 주머니를 채우는 마법사.

대화형(questionary)이 기본이지만, 플래그로 답을 주면 비대화형으로 동작한다
(스크립트·자동화·시연). 자동화+투명성 원칙: 저장 전 요약 확인, hook 연결 제안.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from pouch import paths
from pouch.hosts.base import FileHostAdapter, HostAdapter
from pouch.hosts.registry import (
    all_names,
    detect_file_supported,
    detect_hook_installed,
)
from pouch.init.detect import Environment, detect_environment
from pouch.init.profile import InitAnswers, build_memories
from pouch.memory.store import MemoryStore

console = Console()

_ROLES = ["개발자", "DevOps·인프라", "기획·PM", "디자인", "데이터·ML", "기타"]


def ask_profile(env: Environment) -> InitAnswers:
    """questionary로 역할·스택·작업 스타일을 묻는다(대화형 경로)."""
    import questionary

    role = questionary.select("역할이 어떻게 되세요?", choices=_ROLES).ask()
    detected = {runtime.name for runtime in env.runtimes if runtime.version}
    stack_choices = [
        questionary.Choice(runtime.name, checked=runtime.name in detected)
        for runtime in env.runtimes
    ] or [questionary.Choice("기타")]
    stacks = questionary.checkbox("주력 스택을 골라주세요", choices=stack_choices).ask()
    work_style = questionary.text("작업 스타일을 한 줄로 (선택, 엔터로 건너뛰기):").ask()
    return InitAnswers(
        role=role or "기타",
        stacks=tuple(stacks or ()),
        work_style=(work_style or "").strip() or None,
    )


def init(
    role: str | None = typer.Option(None, "--role", help="역할/직군(주면 비대화형)."),
    stack: list[str] = typer.Option(None, "--stack", help="주력 스택(여러 번 지정 가능)."),
    work_style: str | None = typer.Option(None, "--work-style", help="작업 스타일 한 줄."),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 없이 저장·연결."),
) -> None:
    """환경을 감지하고 프로파일을 기억으로 담는다."""
    env = detect_environment()
    _print_detected(env)

    answers = (
        InitAnswers(role=role, stacks=tuple(stack or ()), work_style=work_style)
        if role is not None
        else ask_profile(env)
    )

    memories = build_memories(answers, env)
    console.print("\n[bold]담을 기억[/bold]")
    for memory in memories:
        console.print(f"  • [cyan]{memory.name}[/cyan] — {memory.description}")

    if not yes and not typer.confirm("\n이대로 저장할까요?", default=True):
        console.print("취소했습니다.")
        raise typer.Exit()

    store = MemoryStore()
    for memory in memories:
        store.save(memory)
    console.print(f"[green]✓[/green] {len(memories)}개 기억을 담았습니다.")

    _maybe_offer_set(answers, yes=yes)
    _maybe_offer_adopt(yes=yes)
    _maybe_offer_boundaries(yes=yes)
    _maybe_link_hook(yes=yes)


def _maybe_offer_boundaries(*, yes: bool) -> None:
    """흔한 안전 경계를 제안한다 — 고른 것만 담긴다(대화형 전용).

    `--yes`(비대화형)에선 건너뛴다: 경계는 감지된 사실이 아니라 사용자가 고르는 선호라,
    확인 없이 강요하지 않는다("지어낸 세트 안 담는다" 철학과 같은 정신 — 기본값 아닌
    물어보기). 이미 걸린 이름은 후보에서 빼 중복 제안을 막는다.
    """
    if yes:
        return

    import questionary

    from pouch.boundary.templates import BOUNDARY_TEMPLATES, to_memory
    from pouch.memory.model import MemoryType

    store = MemoryStore()
    existing = {m.name for m in store.list() if m.type is MemoryType.BOUNDARY}
    candidates = [t for t in BOUNDARY_TEMPLATES if t.name not in existing]
    if not candidates:
        return

    choices = [
        questionary.Choice(f"[{t.direction.value.upper()}] {t.description}", value=t.name)
        for t in candidates
    ]
    picked = questionary.checkbox(
        "🚧 자율성 경계를 걸어둘까요? (스페이스로 고르고 엔터 — 안 골라도 됩니다)",
        choices=choices,
    ).ask()
    if not picked:
        console.print("   경계는 나중에 [cyan]pouch boundary add[/cyan] 로 걸 수 있습니다.")
        return

    by_name = {t.name: t for t in candidates}
    today = date.today()
    for name in picked:
        store.save(to_memory(by_name[name], now=today))
    console.print(f"[green]✓[/green] 경계 {len(picked)}개를 걸었습니다.")


def _maybe_offer_adopt(*, yes: bool) -> None:
    """현재 프로젝트에 Claude 네이티브 메모리가 있으면 pouch로 이관을 제안한다.

    없으면 조용히 지나간다(init은 관문이 아니다). 넘기면 매 세션 주입은 안정 핵심만
    남고(project 세션로그는 리뷰 대기), 네이티브 자동로드는 꺼진다(pouch가 대체) —
    끄는 건 .bak 백업이 있어 가역이다. CLI `pouch memory adopt`와 같은 로직을 공유한다.
    """
    from pouch.memory.commands import apply_adoption, gather_adoption
    from pouch.memory.model import MemoryState

    project_root = paths.find_project_root() or Path.cwd()
    _native_dir, items, _skipped = gather_adoption(project_root)
    if not items:
        return  # 넘길 게 없으면 조용히 지나감

    injected = sum(1 for item in items if item.entry.state is MemoryState.INDEXED)
    console.print(
        f"\n🧠 Claude 네이티브 메모리 [bold]{len(items)}[/bold]건 발견 — "
        f"pouch로 넘기면 매 세션 주입은 {injected}건만(나머지는 주입 안 함·recall 가능)."
    )
    if not yes and not typer.confirm(
        "지금 pouch로 넘길까요? (Claude 자동로드는 꺼집니다)", default=True
    ):
        console.print("   나중에 [cyan]pouch memory adopt[/cyan] 로 넘길 수 있습니다.")
        return

    apply_adoption(project_root, items, disable_native=True)
    console.print(
        f"[green]✓[/green] 네이티브 메모리 {len(items)}건 이관 · 자동로드 껐습니다 "
        "([cyan]pouch memory list[/cyan]로 확인)."
    )


def _maybe_offer_set(answers: InitAnswers, *, yes: bool) -> None:
    """역할·스택에 맞는 시작 세트가 있으면 통째로 제안한다(콜드 스타트 온보딩).

    맞는 세트가 없으면 조용히 지나간다 — 세트는 문이지 관문이 아니다.
    """
    from pouch.catalog.recommend import interest_tokens
    from pouch.sets.commands import offer_matching_set

    offer_matching_set(tokens=interest_tokens(answers), yes=yes)


def _print_detected(env: Environment) -> None:
    console.print("🔍 [bold]감지된 환경[/bold]")
    console.print(f"   OS: {env.os}   shell: {env.shell or '?'}")
    runtimes = ", ".join(f"{r.name} {r.version or '?'}" for r in env.runtimes) or "없음"
    console.print(f"   런타임: {runtimes}")


def _maybe_link_hook(yes: bool) -> None:
    """감지된 에이전트 전체에 연결(hook)을 제안/수행한다.

    `pouch hook install`과 같은 두 배선을 건다: 기억 주입(세션 시작) +
    사용 기록(도구 쓸 때). 사용 기록이 빠지면 진화가 볼 데이터가 안 쌓여
    "쓸수록 진화한다"가 시작조차 못 한다 — init만 돌린 사용자에게 특히 중요.

    이 머신에 있는 호스트만 대상으로 삼는다: 훅 호스트(Claude·Codex, 설정 폴더
    존재)와 파일 호스트(Kiro, 전역 설치). 하나도 못 찾으면 조용히 안내만 남긴다 —
    init은 관문이 아니다.
    """
    hooks = [a for a in detect_hook_installed() if not _hook_fully_linked(a)]
    files = [a for a in detect_file_supported() if not a.is_linked()]
    if not hooks and not files:
        # 이미 다 연결됐거나, 감지된 호스트가 없거나.
        if detect_hook_installed() or detect_file_supported():
            console.print("[green]✓[/green] 감지된 에이전트에 이미 연결돼 있습니다.")
        else:
            console.print(f"   나중에 [cyan]pouch hook install[/cyan] 로 연결할 수 있습니다 ({', '.join(all_names())}).")
        return

    names = ", ".join(a.display_name for a in (*hooks, *files))
    if not yes and not typer.confirm(f"지금 연결할까요? ({names})", default=True):
        console.print("   나중에 [cyan]pouch hook install[/cyan] 로 연결할 수 있습니다.")
        return

    for adapter in hooks:
        _link_hook(adapter)
    if files:
        body = _global_memory_body()
        for file_adapter in files:
            _link_file(file_adapter, body)


def _hook_fully_linked(adapter: HostAdapter) -> bool:
    """훅 호스트에 두 배선이 모두 걸려 있는지."""
    config = adapter.load(adapter.config_path())
    return adapter.is_memory_installed(config) and adapter.is_usage_installed(config)


def _global_memory_body() -> str:
    """파일 호스트에 심을 스냅샷 본문(현재 전역 기억)."""
    from pouch.hosts.filesync import render_file_body

    return render_file_body(list(MemoryStore().list()))


def _link_hook(adapter: HostAdapter) -> None:
    """훅 호스트에 두 배선을 걸고 결과를 출력한다."""
    path = adapter.config_path()
    config = adapter.load(path)
    updated = adapter.with_usage_installed(adapter.with_memory_installed(config))
    adapter.write(path, updated)
    console.print(f"[green]✓[/green] {adapter.display_name} 연결 완료 → {path}")
    _print_notes(adapter)


def _link_file(adapter: FileHostAdapter, body: str) -> None:
    """파일 호스트에 기억 스냅샷을 심고 결과를 출력한다."""
    adapter.link(body)
    console.print(f"[green]✓[/green] {adapter.display_name} 연결 완료 → {adapter.content_path()}")
    _print_notes(adapter)


def _print_notes(adapter: HostAdapter | FileHostAdapter) -> None:
    for note in adapter.post_install_notes():
        console.print(f"   [yellow]![/yellow] {escape(note)}")
