"""세트 내보내기 — 지금 주머니(표면)를 세트 파일로 굳힌다.

apply의 거울상: apply가 "출처에서 가져와 표면에 올린다"면, export는 "지금 표면에
올라온 것을 어디서 가져왔는지로 되적는다". 새 형식이 아니라 같은 StarterSet
(선곡표: source→install)를 실사용으로 닳은 주머니에서 파생한다.

**무엇을 담나 — 표면(active surface).** 내가 실제로 연장통에 올린 한 벌. 표면
자체가 evolve로 닳은 결과라 "실사용에서 굳힘"이 이미 들어있다(sets/builtin/README의
원칙: 지어낸 세트는 안 담는다).

**이식성 — 출처는 홈 상대(`~`).** apply가 `item.source` 경로에서 재import하므로,
같은 플러그인을 가진 다른 머신·유저에서도 동작하도록 홈 아래 경로를 `~/`로 접는다.
이게 raft 공유와 내장 세트 1호의 전제다.

**owned는 본문을 통째로 싣는다(인라인 임베드 — 배승도 락, 2026-07-18).** 직접
만든 도구는 가져올 출처가 없으므로 출처 대신 실물(body)을 세트 파일 안에 품는다.
"남의 도구는 주소, 내 도구는 실물"이 한 파일에 공존한다. v0는 스킬만.

**못 담는 것은 격리 보고(인질 금지).** 건너뛰고 이유를 돌려준다:
- owned인데 스킬이 아니거나 본문이 빈 것 — v0 임베드 범위 밖.
- 연결형(mcp·훅 등 upstream 없음) — 원본 파일 경로를 엔트리가 안 들고 있다.
- surface=plugin — 플러그인이 표면을 관리(apply도 관측만 하는 것과 대칭).

**match_tokens는 담긴 도구에서 파생.** "이 도구들에 관심 있는 사람"과 매칭 —
자기완결(프로필 메모리를 안 읽는다). 추천 풀과 같은 토큰 공간을 쓴다.

순수 함수(build_export_set) — 시계·IO 없다. home은 주입한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pouch.catalog.model import SURFACE_PLUGIN, Ownership, ToolEntry, ToolKind
from pouch.evolution.pool import build_pool
from pouch.sets.model import EmbeddedTool, SetItem, StarterSet

_MATCH_TOKEN_CAP = 20  # 매칭 토큰은 몇 개면 충분 — 전량은 시끄럽다


@dataclass(frozen=True)
class ExportResult:
    """내보내기 결과 — 굳힌 세트 + 못 담아 건너뛴 것(이유 포함)."""

    starter: StarterSet
    skipped: tuple[str, ...]


def _homeify(path_str: str, home: Path) -> str:
    """홈 아래 경로를 `~/`로 접어 이식성 있게. 홈 밖이면 그대로 둔다(순수 경로 계산)."""
    try:
        rel = Path(path_str).relative_to(home)
    except ValueError:
        return path_str
    return f"~/{rel}"


def _match_tokens(entries: list[ToolEntry]) -> tuple[str, ...]:
    """담긴 도구 토큰(설명·태그·id)을 매칭 토큰으로 접는다 — 누구를 위한 세트인지."""
    tokens: set[str] = set()
    for pool_entry in build_pool(entries):
        tokens |= pool_entry.tokens
    return tuple(sorted(tokens))[:_MATCH_TOKEN_CAP]


def build_export_set(
    name: str,
    entries: list[ToolEntry],
    active_ids: set[str],
    *,
    home: Path,
    title: str | None = None,
    description: str = "",
) -> ExportResult:
    """표면(active)에 올린 것 중 재설치 가능한 것을 세트로 굳힌다(순수).

    담을 수 있는 건 재import 출처(upstream)가 있는 것뿐 — owned·연결형·플러그인
    관리 표면은 v0에서 출처가 없어 건너뛰고 이유를 보고한다.
    """
    by_id = {entry.id: entry for entry in entries}
    items: list[SetItem] = []
    exported: list[ToolEntry] = []
    skipped: list[str] = []

    for entry_id in sorted(active_ids):
        entry = by_id.get(entry_id)
        if entry is None:
            continue  # 표면에 있는데 카탈로그에 없음 — 있을 수 없지만 방어적으로 무시
        if entry.surface == SURFACE_PLUGIN:
            skipped.append(f"'{entry_id}'는 플러그인이 표면을 관리해 세트에 안 담음(관측만)")
            continue
        if entry.ownership is Ownership.OWNED:
            # 직접 만든 도구는 출처가 없으니 본문을 통째로 싣는다(인라인 임베드,
            # 2026-07-18 락). v0는 스킬(글 한 장짜리)만 — 나머지는 정직하게 보고.
            if entry.kind is not ToolKind.SKILL:
                skipped.append(f"'{entry_id}'는 owned인데 v0 임베드는 스킬만 담음")
                continue
            if not (entry.body or "").strip():
                skipped.append(f"'{entry_id}'는 owned인데 본문이 비어 있어 못 담음")
                continue
            items.append(SetItem(embed=EmbeddedTool(
                id=entry.id,
                kind=entry.kind.value,
                title=entry.title,
                description=entry.description,
                tags=entry.tags,
                body=entry.body or "",
            )))
            exported.append(entry)
            continue
        if not entry.upstream:
            skipped.append(f"'{entry_id}'는 재설치할 출처 경로가 없음(연결형) — v0 세트엔 못 담음")
            continue
        items.append(SetItem(source=_homeify(entry.upstream, home), install=(entry_id,)))
        exported.append(entry)

    starter = StarterSet(
        name=name,
        title=title or name,
        description=description,
        match_tokens=_match_tokens(exported),
        items=tuple(items),
    )
    return ExportResult(starter=starter, skipped=tuple(skipped))
