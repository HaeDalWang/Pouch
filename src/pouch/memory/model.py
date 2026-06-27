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


class MemoryScope(str, Enum):
    """기억의 적용 범위."""

    GLOBAL = "global"
    PROJECT = "project"


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

    def to_markdown(self) -> str:
        """frontmatter 마크다운 문자열로 직렬화한다."""
        post = frontmatter.Post(
            self.body,
            name=self.name,
            description=self.description,
            type=self.type.value,
            scope=self.scope.value,
            weight=self.weight,
            created=self.created.isoformat(),
        )
        return frontmatter.dumps(post)

    @classmethod
    def from_markdown(cls, name: str, text: str) -> MemoryEntry:
        """frontmatter 마크다운에서 역직렬화한다. `name`은 파일명을 권위로 삼는다."""
        post = frontmatter.loads(text)
        meta = post.metadata
        return cls(
            name=name,
            description=str(meta.get("description", "")),
            body=post.content,
            type=MemoryType(meta["type"]),
            scope=MemoryScope(meta["scope"]),
            weight=int(meta.get("weight", 0)),
            created=_coerce_date(meta.get("created")),
        )


def _coerce_date(value: object) -> date:
    """frontmatter가 date로 파싱했든 문자열이든 안전하게 date로 변환한다."""
    if isinstance(value, date):
        return value
    if value is None:
        return date.today()
    return date.fromisoformat(str(value))
