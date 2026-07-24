"""시작 세트 모델 — 세트 파일을 읽고, 역할·스택 토큰으로 고른다.

세트 파일(JSON) 하나 = 세트 하나. 항목마다 "어디서 가져올지(source)"와
"무엇을 표면에 올릴지(install)"를 담는다 — 콜드 스타트(빈 카탈로그)를
실제로 채우려면 출처까지 담아야 한다(배승도 결정, 2026-07-07).

내장 세트(패키지 동봉)와 사용자 세트(~/.pouch/sets/)를 합쳐 읽되,
같은 이름이면 사용자 것이 이긴다(개인 우선). 매칭 토큰은 지금의
토큰 규칙(영숫자)상 ascii만 유효하다 — 한글 토큰은 매칭에 안 걸린다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from pouch import paths

_BUILTIN_DIR = Path(__file__).parent / "builtin"


@dataclass(frozen=True)
class EmbeddedTool:
    """세트에 통째로 실린 직접 만든 도구(owned) — 출처 대신 본문을 품는다.

    인라인 방식 락(배승도, 2026-07-18): "남의 도구는 주소, 내 도구는 실물"이
    세트 JSON 한 파일에 같이 들어간다. v0는 스킬(글 한 장짜리)만.
    """

    id: str
    body: str
    kind: str = "skill"
    title: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        data: dict = {"id": self.id, "kind": self.kind, "body": self.body}
        if self.title:
            data["title"] = self.title
        if self.description:
            data["description"] = self.description
        if self.tags:
            data["tags"] = list(self.tags)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> EmbeddedTool:
        return cls(
            id=data["id"],
            body=data["body"],  # 본문 없는 embed는 형식 위반 — KeyError로 격리
            kind=data.get("kind", "skill"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            tags=tuple(data.get("tags", ())),
        )


@dataclass(frozen=True)
class RepoRef:
    """저장소 참조 — 몸통 대신 주소를 싣는다 (Phase 4.8 ⑤, 배승도 락 2026-07-24).

    받는 쪽 컴퓨터엔 이 도구가 없을 수 있다 — 대신 "어느 저장소(주소)의 어떤
    도구들"인지를 싣는다. 세트는 도구 모음이라 여러 저장소를 걸칠 수 있다.
    적용은 받는 쪽이 그 저장소를 **직접 등록한 뒤에만**(등록=신뢰 표명이라
    세트가 대신 못 함) — set-export-plugin-mcp-gap을 닫는 길이다.
    """

    name: str  # 저장소 이름 (받는 쪽 repo add에 제안할 이름)
    url: str  # git 주소 — 받는 쪽이 등록할 때 필요
    tools: tuple[str, ...] = ()  # 그 저장소에서 설치할 도구(맨 이름)들

    def to_dict(self) -> dict:
        return {"name": self.name, "url": self.url, "tools": list(self.tools)}

    @classmethod
    def from_dict(cls, data: dict) -> RepoRef:
        return cls(
            name=data["name"],
            url=data["url"],  # 주소 없는 참조는 형식 위반 — KeyError로 격리
            tools=tuple(data.get("tools", ())),
        )


@dataclass(frozen=True)
class SetItem:
    """세트의 한 항목: 참조(source→install) · 임베드(embed) · 저장소(repo) 중 하나.

    참조는 "어디서 가져올지"만 가리키고, 임베드는 본문을 통째로 품고(직접 만든
    도구는 가져올 출처가 없으므로), 저장소는 등록할 주소와 그 안의 도구들을 가리킨다.
    """

    source: str = ""
    install: tuple[str, ...] = ()
    embed: EmbeddedTool | None = None
    repo: RepoRef | None = None

    def to_dict(self) -> dict:
        if self.embed is not None:
            return {"embed": self.embed.to_dict()}
        if self.repo is not None:
            return {"repo": self.repo.to_dict()}
        data: dict = {"source": self.source}
        if self.install:
            data["install"] = list(self.install)
        return data


@dataclass(frozen=True)
class StarterSet:
    """미리 큐레이션된 한 벌 — 가리키는 목록(선곡표)."""

    name: str
    title: str
    description: str
    match_tokens: tuple[str, ...]  # 역할·스택 관심 토큰과 교집합 매칭
    items: tuple[SetItem, ...]

    def to_dict(self) -> dict:
        """세트 JSON으로 직렬화(from_dict의 대칭). 세트 내보내기가 쓴다."""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "match": list(self.match_tokens),
            "items": [item.to_dict() for item in self.items],
        }

    def install_count(self) -> int:
        """표면에 올릴 총 개수 — 참조 install + 임베드 + 저장소 참조의 도구들."""
        refs = sum(len(item.install) for item in self.items)
        embeds = sum(1 for item in self.items if item.embed is not None)
        repo_tools = sum(len(item.repo.tools) for item in self.items if item.repo)
        return refs + embeds + repo_tools

    @classmethod
    def from_dict(cls, data: dict) -> StarterSet:
        return cls(
            name=data["name"],
            title=data.get("title") or data["name"],
            description=data.get("description", ""),
            match_tokens=tuple(t.lower() for t in data.get("match", ())),
            items=tuple(_item_from_dict(item) for item in data.get("items", ())),
        )


def _item_from_dict(item: dict) -> SetItem:
    """항목 하나를 읽는다 — embed(본문 통째)·repo(저장소 참조)·참조(source 필수)."""
    if "embed" in item:
        return SetItem(embed=EmbeddedTool.from_dict(item["embed"]))
    if "repo" in item:
        return SetItem(repo=RepoRef.from_dict(item["repo"]))
    return SetItem(source=item["source"], install=tuple(item.get("install", ())))


def load_set_file(path: Path) -> StarterSet:
    """세트 JSON 파일 하나를 읽는다. 깨졌으면 예외(호출부가 격리 처리)."""
    return StarterSet.from_dict(json.loads(path.read_text(encoding="utf-8")))


def is_safe_set_name(name: str) -> bool:
    """세트 이름이 파일 이름으로 안전한가 — 세트 폴더 탈출 방지(순수).

    이름은 `~/.pouch/sets/<이름>.json` 경로에 그대로 박힌다. import는 **남이 준
    파일**의 이름을 받으므로(받는 문), `../` 같은 상위 탈출이 들어간 이름이면
    세트 폴더 밖 아무 데나 쓸 수 있게 된다 — 그래서 경로 구분자·`..`·숨김
    파일 꼴은 거부한다. 표현(한글 등)은 막지 않는다 — 막는 건 탈출뿐.
    """
    return (
        bool(name)
        and "/" not in name
        and "\\" not in name
        and ".." not in name
        and "\x00" not in name
        and not name.startswith(".")
    )


def available_sets(
    *,
    builtin_dir: Path | None = None,
    user_dir: Path | None = None,
    registry_dir: Path | None = None,
) -> list[StarterSet]:
    """당겨온(레지스트리) + 내장 + 사용자 세트를 모두 읽는다. 같은 이름은 사용자가 이긴다.

    우선순위(같은 이름 충돌 시): registry(남) < builtin < user(나) — 개인 우선.
    당겨온 세트는 `registry/sets/<author>/<name>.json`에 살고, 정체를 `<author>/<name>`로
    스코프해 남끼리·나와 이름이 안 부딪게 한다(작성자 스코프). 깨진 파일은 건너뛴다 —
    한 파일이 전체 목록을 인질로 잡지 않는다.
    """
    builtin = builtin_dir if builtin_dir is not None else _BUILTIN_DIR
    user = user_dir if user_dir is not None else paths.sets_dir()
    registry = registry_dir if registry_dir is not None else paths.registry_dir()

    by_name: dict[str, StarterSet] = {}
    # 레지스트리(남) 먼저 = 가장 낮은 우선. 작성자 스코프 이름으로 정체를 준다.
    reg_sets = registry / "sets"
    if reg_sets.is_dir():
        for path in sorted(reg_sets.glob("*/*.json")):
            try:
                loaded = load_set_file(path)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            scoped = replace(loaded, name=f"{path.parent.name}/{loaded.name}")
            by_name[scoped.name] = scoped
    for directory in (builtin, user):  # 나중(사용자)이 덮는다 = 개인 우선
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                loaded = load_set_file(path)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            by_name[loaded.name] = loaded
    return sorted(by_name.values(), key=lambda s: s.name)


def match_sets(sets: list[StarterSet], *, tokens: set[str]) -> list[StarterSet]:
    """관심 토큰과 겹치는 세트만, 겹침 많은 순으로 돌려준다(순수)."""
    scored = [
        (len(tokens & set(s.match_tokens)), s)
        for s in sets
    ]
    matched = [(score, s) for score, s in scored if score > 0]
    return [s for _, s in sorted(matched, key=lambda pair: (-pair[0], pair[1].name))]
