"""답변 → 메모리 변환 순수 로직 검증.

3축(역할/방향·스타일·경계) + 되비춤(reflect). 판정 없이 열린 user 기억으로 저장하고,
경계만 boundary 타입(deny·user 출처)으로 갈린다.
"""

from __future__ import annotations

from pouch.init.detect import Environment, Runtime
from pouch.init.profile import InitAnswers, build_memories, reflect
from pouch.memory.model import Direction, MemoryScope, MemoryType, SOURCE_USER


def _env() -> Environment:
    return Environment(
        os="Darwin",
        shell="/bin/zsh",
        git_email="e@x.com",
        runtimes=(Runtime("python", "3.11"), Runtime("go", "1.26")),
        has_claude=True,
    )


def _answers(**kw: object) -> InitAnswers:
    base = dict(role="인프라 하다 앱 개발로", stacks=("python", "go"), style="dry", boundary=None)
    base.update(kw)
    return InitAnswers(**base)  # type: ignore[arg-type]


def test_role_memory_keeps_free_text() -> None:
    memories = build_memories(_answers(role="디자이너인데 코드 배우는 중"), _env())
    role = next(m for m in memories if m.name == "role")
    assert "디자이너인데 코드 배우는 중" in role.body


def test_style_produces_directive_body() -> None:
    # Arrange — 건조 스타일
    memories = build_memories(_answers(style="dry"), _env())

    # Assert — 본문이 에이전트가 따를 지시문(건조/맞는 말만)
    style = next(m for m in memories if m.name == "style")
    assert style.type is MemoryType.USER
    assert "건조" in style.body


def test_style_omitted_when_none() -> None:
    names = {m.name for m in build_memories(_answers(style=None), _env())}
    assert "style" not in names


def test_boundary_omitted_when_blank() -> None:
    # 경계를 안 적으면 줄 자체가 없다(엔터 스킵).
    names = {m.name for m in build_memories(_answers(boundary=None), _env())}
    assert "boundary" not in names


def test_boundary_is_deny_user_global() -> None:
    # Arrange — 경계 한 줄
    memories = build_memories(_answers(boundary="프로덕션 DB엔 손대지 마"), _env())

    # Assert — boundary 타입, deny 방향, 사람이 건 출처, 전역
    boundary = next(m for m in memories if m.name == "boundary")
    assert boundary.type is MemoryType.BOUNDARY
    assert boundary.direction is Direction.DENY
    assert boundary.source == SOURCE_USER
    assert boundary.scope is MemoryScope.GLOBAL
    assert "프로덕션 DB엔 손대지 마" in boundary.body


def test_boundary_description_carries_content() -> None:
    # 상태화면 미리보기가 다른 축(역할·환경)과 결이 맞게, 라벨이 아니라 내용을 담는다.
    memories = build_memories(_answers(boundary="terraform apply"), _env())
    boundary = next(m for m in memories if m.name == "boundary")
    assert "terraform apply" in boundary.description


def test_non_boundary_memories_are_global_user() -> None:
    memories = build_memories(_answers(boundary="x"), _env())
    non_boundary = [m for m in memories if m.type is not MemoryType.BOUNDARY]
    assert all(m.scope is MemoryScope.GLOBAL for m in non_boundary)
    assert all(m.type is MemoryType.USER for m in non_boundary)


def test_environment_memory_mentions_os_and_runtime() -> None:
    memories = build_memories(_answers(), _env())
    env_memory = next(m for m in memories if m.name == "environment")
    assert "Darwin" in env_memory.body
    assert "python 3.11" in env_memory.body


def test_stack_omitted_when_empty() -> None:
    names = {m.name for m in build_memories(_answers(stacks=()), _env())}
    assert "stack" not in names


def test_reflect_echoes_role_and_detected_runtime() -> None:
    # 되비춤은 사용자 말(역할)을 그대로 되읽고 + 감지 사실을 얹는다(recognition).
    lines = reflect(_answers(role="인프라 하다 앱 개발로", style="dry"), _env())
    text = "\n".join(lines)
    assert "인프라 하다 앱 개발로" in text
    assert "python" in text  # 감지된 런타임이 되비침에 들어온다


def test_reflect_includes_boundary_when_present() -> None:
    lines = reflect(_answers(boundary="프로덕션 DB엔 손대지 마"), _env())
    assert any("프로덕션 DB엔 손대지 마" in line for line in lines)
