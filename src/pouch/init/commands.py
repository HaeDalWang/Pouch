"""`pouch init` — 환경을 감지하고 나에게 맞춰 주머니를 채우는 마법사.

대화형(questionary)이 기본이지만, 플래그로 답을 주면 비대화형으로 동작한다
(스크립트·자동화·시연). 자동화+투명성 원칙: 저장 전 요약 확인, hook 연결 제안.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.markup import escape

from pouch.confirm import confirm
from pouch import paths
from pouch.hosts.base import FileHostAdapter, HostAdapter
from pouch.hosts.registry import (
    all_names,
    detect_file_supported,
    detect_hook_installed,
)
from pouch.init.detect import Environment, detect_environment
from pouch.init.profile import InitAnswers, build_memories, reflect
from pouch.memory.store import MemoryStore

if TYPE_CHECKING:
    from pouch.catalog.model import ToolEntry
    from pouch.evolution.usage_log import UsageEvent

console = Console()

# 스타일 선택지 — 라벨(사람이 고름) → 키(profile이 지시문으로 변환).
_STYLE_CHOICES = [
    ("친절하게, 맥락 설명하면서", "warm"),
    ("짧고 건조하게, 맞는 말만", "dry"),
    ("중간", "mid"),
]


def ask_profile(env: Environment) -> InitAnswers:
    """questionary로 세 축(역할/방향·스타일·경계)을 묻는다(대화형 경로).

    역할은 고정 선택지가 아니라 자유 입력이다 — 감지가 자신있게 틀리는 자리라
    (역할·궤적) 사람 말로 받는다. 경계는 비우면(엔터) 줄을 안 만든다.
    """
    import questionary

    role = questionary.text(
        "지금 주로 뭘 하고, 앞으로 뭘 해보고 싶으세요?"
    ).ask()
    detected = {runtime.name for runtime in env.runtimes if runtime.version}
    stack_choices = [
        questionary.Choice(runtime.name, checked=runtime.name in detected)
        for runtime in env.runtimes
    ] or [questionary.Choice("기타")]
    stacks = questionary.checkbox("주력 스택을 골라주세요", choices=stack_choices).ask()
    style_label = questionary.select(
        "에이전트가 어떻게 말했으면 좋겠어요?",
        choices=[label for label, _ in _STYLE_CHOICES],
    ).ask()
    boundary = questionary.text(
        "절대 안 했으면 하는 거 있어요? (나중에 바꿀 수 있어요 · 엔터로 건너뛰기)"
    ).ask()
    return InitAnswers(
        role=(role or "").strip() or "미입력",
        stacks=tuple(stacks or ()),
        style=_style_key(style_label),
        boundary=(boundary or "").strip() or None,
    )


def _style_key(label: str | None) -> str | None:
    """선택 라벨을 profile이 아는 스타일 키로 되돌린다."""
    for choice_label, key in _STYLE_CHOICES:
        if choice_label == label:
            return key
    return None


def init(
    role: str | None = typer.Option(None, "--role", help="지금 하는 일·방향(주면 비대화형)."),
    stack: list[str] = typer.Option(None, "--stack", help="주력 스택(여러 번 지정 가능)."),
    style: str | None = typer.Option(None, "--style", help="말투: warm/dry/mid."),
    boundary: str | None = typer.Option(None, "--boundary", help="절대 안 했으면 하는 것 한 줄."),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 없이 저장·연결."),
) -> None:
    """환경을 감지하고 프로파일을 기억으로 담는다."""
    env = detect_environment()
    _print_detected(env)

    answers = (
        InitAnswers(
            role=role, stacks=tuple(stack or ()), style=style, boundary=boundary
        )
        if role is not None
        else ask_profile(env)
    )

    # 되비춤 — 답을 2인칭 서사로 되읽어준다(판정 아님, recognition).
    console.print()
    for line in reflect(answers, env):
        console.print(f"  {escape(line)}")

    if not yes and not confirm("\n맞아요? 이대로 담을까요?", default=True):
        console.print("취소했습니다.")
        raise typer.Exit()

    memories = build_memories(answers, env)

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
    남고(project 세션로그는 리뷰 대기), **네이티브는 안전망으로 그대로 둔다**(기본은
    옮기기만) — 다른 도구 설정을 기본으로 끄는 건 공격적이고, 새 기억이 흘러들 쓰기
    길이 실사용으로 검증된 뒤 별도 조각에서 끄기를 기본화한다. 완전 대체는 사용자가
    `pouch memory adopt --disable-native`로 명시 선택. CLI adopt와 같은 로직을 공유한다.
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
    if not yes and not confirm(
        "지금 pouch로 넘길까요? (원본·Claude 자동로드는 안전망으로 그대로 둡니다)", default=True
    ):
        console.print("   나중에 [cyan]pouch memory adopt[/cyan] 로 넘길 수 있습니다.")
        return

    apply_adoption(project_root, items, disable_native=False)
    console.print(
        f"[green]✓[/green] 네이티브 메모리 {len(items)}건을 pouch로 옮겼습니다 "
        "(Claude 자동로드는 안전망으로 그대로 — 완전 대체는 "
        "[cyan]pouch memory adopt --disable-native[/cyan])."
    )


def _offer_tokens(
    answers: InitAnswers, events: list[UsageEvent], entries: list[ToolEntry]
) -> set[str]:
    """세트 매칭에 쓸 관심 토큰 — 답변(stated) ∪ 실사용으로 배운 것(learned)(순수).

    콜드 스타트(사용 이력 없음)면 learned=∅ → 답변만으로 매칭(자연 폴백). 재실행
    사용자는 손에 맞은 도구가 배운 관심사까지 얹혀 더 잘 맞는 세트를 만난다
    (개인화 학습 레인 1, Phase 4.5).
    """
    from pouch.catalog.model import alias_map
    from pouch.catalog.recommend import interest_tokens
    from pouch.evolution.learned_profile import learned_interest_tokens

    learned = learned_interest_tokens(events, entries, alias_map=alias_map(entries))
    return interest_tokens(answers) | learned


def _maybe_offer_set(answers: InitAnswers, *, yes: bool) -> None:
    """역할·스택에 맞는 시작 세트가 있으면 통째로 제안한다(콜드 스타트 온보딩).

    맞는 세트가 없으면 조용히 지나간다 — 세트는 문이지 관문이 아니다.
    """
    from pouch.catalog.store import CatalogStore
    from pouch.evolution.usage_log import read_events
    from pouch.sets.commands import offer_matching_set

    entries = list(CatalogStore().list())
    tokens = _offer_tokens(answers, read_events(), entries)
    offer_matching_set(tokens=tokens, yes=yes)


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
    if not yes and not confirm(f"지금 연결할까요? ({names})", default=True):
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
