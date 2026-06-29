"""답변 → 메모리 변환 순수 로직 검증."""

from __future__ import annotations

from pouch.init.detect import Environment, Runtime
from pouch.init.profile import InitAnswers, build_memories
from pouch.memory.model import MemoryScope, MemoryType


def _env() -> Environment:
    return Environment(
        os="Darwin",
        shell="/bin/zsh",
        git_email="e@x.com",
        runtimes=(Runtime("python", "3.11"), Runtime("go", "1.26")),
        has_claude=True,
    )


def test_build_includes_all_when_present() -> None:
    # Arrange
    answers = InitAnswers(role="개발자", stacks=("python", "go"), work_style="테스트 먼저")

    # Act
    memories = build_memories(answers, _env())

    # Assert
    names = {memory.name for memory in memories}
    assert names == {"role", "environment", "stack", "work-style"}


def test_all_memories_are_global_user() -> None:
    memories = build_memories(InitAnswers("개발자", ("python",), None), _env())
    assert all(m.scope is MemoryScope.GLOBAL for m in memories)
    assert all(m.type is MemoryType.USER for m in memories)


def test_optional_fields_omitted_when_empty() -> None:
    # Arrange — 스택·작업스타일 비움
    answers = InitAnswers(role="기획·PM", stacks=(), work_style=None)

    # Act
    names = {memory.name for memory in build_memories(answers, _env())}

    # Assert
    assert "stack" not in names
    assert "work-style" not in names
    assert {"role", "environment"} <= names


def test_environment_memory_mentions_os_and_runtime() -> None:
    memories = build_memories(InitAnswers("개발자", (), None), _env())
    env_memory = next(m for m in memories if m.name == "environment")
    assert "Darwin" in env_memory.body
    assert "python 3.11" in env_memory.body
