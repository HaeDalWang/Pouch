"""카탈로그 도메인 모델.

ownership이 "pouch와 도구의 관계"를 가른다 — 판별 기준은 "추적할 upstream이 있느냐":
- owned    : upstream 없음. body를 직접 소유, mutate 자유.
- vendored : upstream 있음. body는 들지 않고(불변 sync 참조) 개인화는 overlay에 분리.
- linked   : 외부 실행 인프라. recipe + region만 등록, 실행은 위임.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import frontmatter


class ToolKind(str, Enum):
    """아티팩트 종류."""

    SKILL = "skill"
    COMMAND = "command"
    AGENT = "agent"
    RULE = "rule"
    HOOK = "hook"
    MCP = "mcp"


class Ownership(str, Enum):
    """pouch와 도구의 관계."""

    OWNED = "owned"
    VENDORED = "vendored"
    LINKED = "linked"


@dataclass(frozen=True)
class Overlay:
    """vendored 본체 위에 쌓는 개인화 레이어(본체와 분리 필수)."""

    tags: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()  # boundary 메모리 id 참조
    notes: str | None = None

    def to_dict(self) -> dict:
        data: dict = {}
        if self.tags:
            data["tags"] = list(self.tags)
        if self.boundaries:
            data["boundaries"] = list(self.boundaries)
        if self.notes:
            data["notes"] = self.notes
        return data

    @classmethod
    def from_dict(cls, data: dict | None) -> Overlay:
        data = data or {}
        return cls(
            tags=tuple(data.get("tags", ())),
            boundaries=tuple(data.get("boundaries", ())),
            notes=data.get("notes"),
        )


@dataclass(frozen=True)
class ToolEntry:
    """카탈로그 항목(불변). ownership별 필드는 해당 안 되면 None."""

    id: str
    kind: ToolKind
    ownership: Ownership
    source: str
    title: str
    description: str
    tags: tuple[str, ...] = ()
    body: str | None = None  # owned
    upstream: str | None = None  # vendored
    synced_at: str | None = None  # vendored
    overlay: Overlay | None = None  # vendored
    recipe: dict | None = None  # linked
    region: str | None = None  # linked

    @classmethod
    def owned(
        cls,
        *,
        id: str,
        kind: ToolKind,
        source: str,
        title: str,
        description: str,
        body: str,
        tags: tuple[str, ...] = (),
    ) -> ToolEntry:
        return cls(
            id=id,
            kind=kind,
            ownership=Ownership.OWNED,
            source=source,
            title=title,
            description=description,
            tags=tuple(tags),
            body=body,
        )

    @classmethod
    def vendored(
        cls,
        *,
        id: str,
        kind: ToolKind,
        source: str,
        title: str,
        description: str,
        upstream: str,
        tags: tuple[str, ...] = (),
        overlay: Overlay | None = None,
        synced_at: str | None = None,
    ) -> ToolEntry:
        return cls(
            id=id,
            kind=kind,
            ownership=Ownership.VENDORED,
            source=source,
            title=title,
            description=description,
            tags=tuple(tags),
            upstream=upstream,
            synced_at=synced_at,
            overlay=overlay,
        )

    @classmethod
    def linked(
        cls,
        *,
        id: str,
        kind: ToolKind,
        source: str,
        title: str,
        description: str,
        recipe: dict,
        region: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> ToolEntry:
        return cls(
            id=id,
            kind=kind,
            ownership=Ownership.LINKED,
            source=source,
            title=title,
            description=description,
            tags=tuple(tags),
            recipe=recipe,
            region=region,
        )

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def to_markdown(self) -> str:
        """frontmatter 마크다운으로 직렬화. owned만 본문(body)을 가진다."""
        meta: dict = {
            "id": self.id,
            "kind": self.kind.value,
            "ownership": self.ownership.value,
            "source": self.source,
            "title": self.title,
            "description": self.description,
        }
        if self.tags:
            meta["tags"] = list(self.tags)
        if self.upstream:
            meta["upstream"] = self.upstream
        if self.synced_at:
            meta["synced_at"] = self.synced_at
        if self.overlay and self.overlay.to_dict():
            meta["overlay"] = self.overlay.to_dict()
        if self.recipe:
            meta["recipe"] = self.recipe
        if self.region:
            meta["region"] = self.region
        return frontmatter.dumps(frontmatter.Post(self.body or "", **meta))

    @classmethod
    def from_markdown(cls, text: str) -> ToolEntry:
        post = frontmatter.loads(text)
        meta = post.metadata
        ownership = Ownership(meta["ownership"])
        overlay = Overlay.from_dict(meta["overlay"]) if meta.get("overlay") else None
        body = post.content if ownership is Ownership.OWNED and post.content.strip() else None
        return cls(
            id=meta["id"],
            kind=ToolKind(meta["kind"]),
            ownership=ownership,
            source=meta.get("source", ""),
            title=meta.get("title", ""),
            description=meta.get("description", ""),
            tags=tuple(meta.get("tags", ())),
            body=body,
            upstream=meta.get("upstream"),
            synced_at=meta.get("synced_at"),
            overlay=overlay,
            recipe=meta.get("recipe"),
            region=meta.get("region"),
        )
