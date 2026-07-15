"""마법사 답변 → 메모리 변환 (순수 로직).

questionary 대화와 분리해 단위 테스트 가능하게 둔다. 세 축을 묻는다:
역할/방향(자유 입력) · 스타일(선택) · 경계(자유, 비면 스킵). 판정하지 않고
열린 `user` 기억으로 쌓되, 경계만 `boundary` 타입(deny·사람 출처)으로 갈린다.

`reflect`는 저장 직전 답을 2인칭 서사로 되읽어준다(recognition) — 판정이 아니라
"이게 날 아네"의 순간. substance는 질문 수가 아니라 이 되비춤에서 나온다.
"""

from __future__ import annotations

from dataclasses import dataclass

from pouch.init.detect import Environment
from pouch.memory.model import (
    Direction,
    MemoryEntry,
    MemoryScope,
    MemoryType,
    SOURCE_USER,
)

# 스타일 선택지 → 에이전트가 따를 지시문 본문.
_STYLE_DIRECTIVES: dict[str, str] = {
    "warm": "친절하게, 맥락을 설명하면서 말해줘.",
    "dry": "짧고 건조하게, 맞는 말만 해줘.",
    "mid": "너무 장황하지도 건조하지도 않게, 중간 정도로 말해줘.",
}


@dataclass(frozen=True)
class InitAnswers:
    """마법사가 수집한(또는 플래그로 받은) 답변.

    role: 지금 뭘 하고 어디로 가는지(자유 입력, 역할·궤적 한 축).
    stacks: 주력 스택(감지 기반 선택).
    style: 말투 선택지 키(warm/dry/mid) 또는 None.
    boundary: 절대 안 했으면 하는 것(자유, 비면 None → 줄 안 만듦).
    """

    role: str
    stacks: tuple[str, ...]
    style: str | None
    boundary: str | None


def _user_memory(name: str, description: str, body: str) -> MemoryEntry:
    return MemoryEntry(
        name=name,
        description=description,
        body=body,
        type=MemoryType.USER,
        scope=MemoryScope.GLOBAL,
    )


def build_memories(answers: InitAnswers, env: Environment) -> list[MemoryEntry]:
    """답변과 감지 환경을 글로벌 기억 목록으로 변환한다.

    role·stack·style·environment는 `user`, 경계만 `boundary`(deny·사람 출처).
    비면 그 줄을 아예 만들지 않는다 — 저마찰 유입(빈 답이 기억을 오염 안 함).
    """
    memories = [
        _user_memory(
            "role",
            f"역할·방향: {answers.role}",
            f"사용자가 지금 하는 일과 가고 싶은 방향: {answers.role}",
        ),
        _user_memory("environment", _environment_summary(env), _environment_body(env)),
    ]
    if answers.stacks:
        joined = ", ".join(answers.stacks)
        memories.append(
            _user_memory("stack", f"주력 스택: {joined}", f"주로 사용하는 언어/스택: {joined}.")
        )
    if answers.style and answers.style in _STYLE_DIRECTIVES:
        memories.append(
            _user_memory("style", "선호하는 말투", _STYLE_DIRECTIVES[answers.style])
        )
    if answers.boundary:
        memories.append(_boundary_memory(answers.boundary))
    return memories


def _boundary_memory(text: str) -> MemoryEntry:
    """사용자가 직접 그은 경계 — deny 방향, 사람 출처(도구 drop과 무관하게 잔존)."""
    return MemoryEntry(
        name="boundary",
        description=f"안 건드릴 것: {text}",
        body=text,
        type=MemoryType.BOUNDARY,
        scope=MemoryScope.GLOBAL,
        direction=Direction.DENY,
        source=SOURCE_USER,
    )


def reflect(answers: InitAnswers, env: Environment) -> list[str]:
    """저장 직전 답을 2인칭 서사로 되읽는다(recognition, 판정 아님)."""
    lines = [f"{answers.role}, 이렇게 일하고 있구나."]
    if answers.style and answers.style in _STYLE_DIRECTIVES:
        lines.append(_STYLE_DIRECTIVES[answers.style].rstrip("."))
    detected = ", ".join(r.name for r in env.runtimes if r.version)
    if detected:
        lines.append(f"{detected} 감지됐어.")
    if answers.boundary:
        lines.append(f"그리고 이건 안 건드릴게 — {answers.boundary}")
    return lines


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
