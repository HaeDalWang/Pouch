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

from pouch.memory.model import Direction, MemoryScope


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


# 표면 통제권 — ownership(몸의 소유)과 직교하는 축. 값이 없으면(None) pouch가
# 표면을 관리한다(install/uninstall 가능). "plugin"이면 플러그인 시스템이
# 표면을 관리하므로 pouch는 관측만 한다(중복 등록·거짓 drop 방지).
SURFACE_PLUGIN = "plugin"


@dataclass(frozen=True)
class RecommendedBoundary:
    """엔트리가 딸고 오는 권장 boundary의 씨앗.

    도구 파일엔 boundary 선언 필드가 없다(산문에서 뽑으면 deny 오독 위험). 그래서
    이건 큐레이터(사람, 나중엔 시작 세트)가 엔트리에 명시적으로 붙인 씨앗이다.
    설치 시 recommended_boundary_memories가 이걸 진짜 boundary 메모리로 태어나게
    하며 source=vendored:<엔트리id>를 도장 찍는다 — 그게 drop gate의 열쇠다.

    방향·스코프는 메모리 타입을 그대로 재사용한다(카탈로그→메모리 정방향 의존).
    """

    name: str
    description: str
    body: str
    direction: Direction
    scope: MemoryScope = MemoryScope.GLOBAL

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "body": self.body,
            "direction": self.direction.value,
            "scope": self.scope.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RecommendedBoundary:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            body=data.get("body", ""),
            direction=Direction(data["direction"]),
            scope=MemoryScope(data.get("scope", MemoryScope.GLOBAL.value)),
        )


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
    aliases: tuple[str, ...] = ()  # 런타임 별칭(usage 추적이 보는 이름) — 예: plugin_<플러그인>_<서버>
    surface: str | None = None  # 표면 통제권: None=pouch 관리, SURFACE_PLUGIN=플러그인 관리(관측만)
    recommended_boundaries: tuple[RecommendedBoundary, ...] = ()  # 딸고 오는 권장 boundary 씨앗

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
        aliases: tuple[str, ...] = (),
        surface: str | None = None,
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
            aliases=tuple(aliases),
            surface=surface,
        )

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def with_recommended_boundaries(
        self, recs: tuple[RecommendedBoundary, ...] | list[RecommendedBoundary]
    ) -> ToolEntry:
        """권장 boundary를 붙인 새 엔트리를 반환한다(불변)."""
        from dataclasses import replace

        return replace(self, recommended_boundaries=tuple(recs))

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
        if self.aliases:
            meta["aliases"] = list(self.aliases)
        if self.surface:
            meta["surface"] = self.surface
        if self.recommended_boundaries:
            meta["recommended_boundaries"] = [
                rec.to_dict() for rec in self.recommended_boundaries
            ]
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
            aliases=tuple(meta.get("aliases", ())),
            surface=meta.get("surface"),
            recommended_boundaries=tuple(
                RecommendedBoundary.from_dict(r)
                for r in meta.get("recommended_boundaries", ())
            ),
        )


def alias_map(entries: list[ToolEntry] | tuple[ToolEntry, ...]) -> dict[str, str]:
    """런타임 별칭 → 카탈로그 정식 id 매핑을 만든다(순수).

    usage.jsonl의 entry_id(예: plugin_ecc_exa)를 카탈로그 엔트리(exa)로 잇는
    다리다 — 이 매핑이 없으면 같은 도구가 "주머니 밖"으로 오인된다.
    """
    return {alias: entry.id for entry in entries for alias in entry.aliases}
