"""메모리 도메인 모델.

한 메모리 = YAML frontmatter + 본문 마크다운. 불변(frozen) 값 객체로 다룬다.
파일 이름이 곧 메모리의 `name`이므로 frontmatter의 name은 보조 정보다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

import frontmatter


class MemoryType(str, Enum):
    """기억의 성격. Claude 네이티브 메모리 분류와 호환된다."""

    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"
    BOUNDARY = "boundary"  # 자율성/신뢰 경계 (허용·확인·금지). context 최상단 강조.


class MemoryScope(str, Enum):
    """기억의 적용 범위."""

    GLOBAL = "global"
    PROJECT = "project"


class Direction(str, Enum):
    """boundary의 방향 — 허용·확인·금지.

    도구를 내릴(drop) 때 이 방향이 처리를 가른다:
    - ALLOW: 도구가 딸고 온 허용은 도구와 함께 내려간다(허용은 좁게).
    - ASK/DENY: 도구가 내려가도 잔존한다(금지·확인은 넓게 — 안전 쪽).

    필드가 None인 옛/방향불명 boundary는 gate에서 잔존으로 안전하게 취급한다.
    산문에서 방향을 기계가 뽑지 않는다 — deny 오독 위험이라 명시 필드로만 읽는다.
    """

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


# boundary의 출처 — drop gate가 "무엇을 남길지" 가르는 축.
# 기본은 사람이 직접 건 것(SOURCE_USER)이라 도구를 내려도 무조건 잔존한다.
# 도구가 딸고 온 것은 "vendored:<도구id>"로 새겨, 그 도구 drop 시 방향에 따라 처리.
SOURCE_USER = "user"
VENDORED_SOURCE_PREFIX = "vendored:"


class MemoryState(str, Enum):
    """기억의 생명 계층 — "drop ≠ 삭제"의 기억판.

    삭제(Deleted)는 파일 부재라 저장 상태가 아니다. 저장되는 건 세 계층 중
    주입 여부가 갈리는 셋: INDEXED만 MEMORY.md에 실려 매 세션 주입되고,
    PENDING(저마찰 포착·미확인)·ARCHIVED(위생으로 강등)는 파일로 남아
    recall로만 소환된다. 하위호환 기본값은 INDEXED(옛 메모리는 전부 활성).
    """

    PENDING = "pending"  # 스테이징 — 확인 전, 주입 안 함(들어오는 문)
    INDEXED = "indexed"  # 활성 — MEMORY.md에 실려 주입됨
    ARCHIVED = "archived"  # 강등 — 인덱스에서 내렸으나 파일·recall 생존(나가는 문)


@dataclass(frozen=True)
class MemoryEntry:
    """단일 메모리 항목(불변)."""

    name: str
    description: str
    body: str
    type: MemoryType
    scope: MemoryScope
    weight: int = 0
    created: date = field(default_factory=date.today)
    state: MemoryState = MemoryState.INDEXED
    last_recalled: date | None = None  # recall 이벤트가 갱신(구조 슬롯; 빈도-면역 로직은 defer)
    direction: Direction | None = None  # boundary 전용. None=방향불명(gate에서 잔존)
    source: str = SOURCE_USER  # boundary 출처. "user" 또는 "vendored:<도구id>"

    def to_markdown(self) -> str:
        """frontmatter 마크다운 문자열로 직렬화한다.

        state=INDEXED·last_recalled=None은 기본값이라 생략한다 — 기존 메모리
        파일에 잡음을 안 남기고, 없으면 로드 시 기본값으로 복원된다(하위호환).
        """
        meta: dict = {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "scope": self.scope.value,
            "weight": self.weight,
            "created": self.created.isoformat(),
        }
        if self.state is not MemoryState.INDEXED:
            meta["state"] = self.state.value
        if self.last_recalled is not None:
            meta["last_recalled"] = self.last_recalled.isoformat()
        if self.direction is not None:
            meta["direction"] = self.direction.value
        if self.source != SOURCE_USER:
            meta["source"] = self.source
        return frontmatter.dumps(frontmatter.Post(self.body, **meta))

    @classmethod
    def from_markdown(cls, name: str, text: str) -> MemoryEntry:
        """frontmatter 마크다운에서 역직렬화한다. `name`은 파일명을 권위로 삼는다."""
        post = frontmatter.loads(text)
        meta = post.metadata
        last_recalled = meta.get("last_recalled")
        direction = meta.get("direction")
        return cls(
            name=name,
            description=str(meta.get("description", "")),
            body=post.content,
            type=MemoryType(meta["type"]),
            scope=MemoryScope(meta["scope"]),
            weight=int(meta.get("weight", 0)),
            created=_coerce_date(meta.get("created")),
            state=MemoryState(meta.get("state", MemoryState.INDEXED.value)),
            last_recalled=_coerce_date(last_recalled) if last_recalled is not None else None,
            direction=Direction(direction) if direction is not None else None,
            source=str(meta.get("source", SOURCE_USER)),
        )


def _coerce_date(value: object) -> date:
    """frontmatter가 date로 파싱했든 문자열이든 안전하게 date로 변환한다."""
    if isinstance(value, date):
        return value
    if value is None:
        return date.today()
    return date.fromisoformat(str(value))
