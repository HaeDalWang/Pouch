"""흔한 자율성 경계 템플릿 — init 온보딩이 제안한다(강요가 아니라 제안).

"지어낸 정답 세트는 안 담는다"는 pouch 철학과 닿는 지점이라 두 가지를 지킨다:
  (1) 생산성 큐레이션이 아니라 near-universal한 **안전** 경계만 담는다.
  (2) 기본값이 아니라 **사용자가 고른 것만** boundary 메모리로 태어난다(출처=user).

목록이 작고 안전에 국한된 이유 — 경계는 "옆 사람에게도 맞을 정답"이 아니라 각자의
자율 범위 선언이라, pouch가 대신 정하면 안 된다. 여기 있는 건 되돌리기 어려운 사고를
막는 최소한의 씨앗일 뿐, 진짜 경계는 실사용에서 사람이 손수 건다(pouch boundary add).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pouch.memory.model import Direction, MemoryEntry, MemoryScope, MemoryType


@dataclass(frozen=True)
class BoundaryTemplate:
    """제안용 경계 씨앗. 고르면 to_memory로 진짜 boundary 메모리가 된다."""

    name: str
    description: str
    direction: Direction
    body: str


# 안전 경계만, near-universal한 것만. 전역(어디서나 적용) 스코프다.
BOUNDARY_TEMPLATES: tuple[BoundaryTemplate, ...] = (
    BoundaryTemplate(
        name="no-force-push-main",
        description="main·master에 force push 금지",
        direction=Direction.DENY,
        body="main/master 브랜치에 force push 하지 않는다. 히스토리 덮어쓰기는 되돌리기 어렵다.",
    ),
    BoundaryTemplate(
        name="ask-before-prod",
        description="prod 배포·변경 전 확인",
        direction=Direction.ASK,
        body="프로덕션에 영향을 주는 배포·삭제·변경 전에는 사용자에게 먼저 확인한다.",
    ),
    BoundaryTemplate(
        name="no-secret-commit",
        description="자격증명 커밋 금지",
        direction=Direction.DENY,
        body="API 키·비밀번호·토큰 등 자격증명을 코드나 커밋·로그에 넣지 않는다.",
    ),
)


def to_memory(template: BoundaryTemplate, *, now: date) -> MemoryEntry:
    """템플릿을 진짜 boundary 메모리로 만든다. 출처는 기본값(user) — 사람이 고른 것이니까."""
    return MemoryEntry(
        name=template.name,
        description=template.description,
        body=template.body,
        type=MemoryType.BOUNDARY,
        scope=MemoryScope.GLOBAL,
        direction=template.direction,
        created=now,
    )
