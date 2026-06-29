"""마법사 답변 → 메모리 변환 (순수 로직).

questionary 대화와 분리해 단위 테스트 가능하게 둔다.
모든 프로파일 기억은 글로벌 `user` 스코프로 저장한다(사용자 자체 장기기억).
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.init.detect import Environment
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


@dataclass(frozen=True)
class InitAnswers:
    """마법사가 수집한(또는 플래그로 받은) 답변."""

    role: str
    stacks: tuple[str, ...]
    work_style: str | None


def _user_memory(name: str, description: str, body: str) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=description,
        body=body,
        type=MemoryType.USER,
        scope=MemoryScope.GLOBAL,
    )


def build_memories(answers: InitAnswers, env: Environment) -> list[MemoryEntry]:
    """답변과 감지 환경을 글로벌 user 메모리 목록으로 변환한다."""
    memories = [
        _user_memory(
            "role",
            f"역할: {answers.role}",
            f"사용자의 역할/직군은 {answers.role}이다.",
        ),
        _user_memory(
            "environment",
            _environment_summary(env),
            _environment_body(env),
        ),
    ]
    if answers.stacks:
        joined = ", ".join(answers.stacks)
        memories.append(
            _user_memory("stack", f"주력 스택: {joined}", f"주로 사용하는 언어/스택: {joined}.")
        )
    if answers.work_style:
        memories.append(_user_memory("work-style", "작업 스타일", answers.work_style))
    return memories


def _environment_summary(env: Environment) -> str:
    runtimes = ", ".join(_runtime_label(name, ver) for name, ver in _runtime_pairs(env))
    return f"환경: {env.os}" + (f" · {runtimes}" if runtimes else "")


def _environment_body(env: Environment) -> str:
    runtimes = ", ".join(_runtime_label(name, ver) for name, ver in _runtime_pairs(env))
    lines = [f"OS: {env.os}"]
    if env.shell:
        lines.append(f"shell: {env.shell}")
    if runtimes:
        lines.append(f"런타임: {runtimes}")
    return "\n".join(lines)


def _runtime_pairs(env: Environment) -> list[tuple[str, str | None]]:
    return [(runtime.name, runtime.version) for runtime in env.runtimes]


def _runtime_label(name: str, version: str | None) -> str:
    return f"{name} {version}" if version else name
