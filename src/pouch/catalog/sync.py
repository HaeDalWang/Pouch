"""sync — vendored 엔트리의 upstream을 재방문해 카탈로그를 최신으로 맞춘다.

import이 '처음 들이기'라면 sync는 '재방문'이다. body는 애초에 안 들고 있으니
(vendored) frontmatter만 다시 읽어 metadata와 synced_at을 갱신한다.
개인화(overlay)는 import_vendored_skill이 보존하므로 그대로 살아남는다.

층 구분 — "body는 자동 이사, boundary는 flag만" (2026-07-05 결정):
  - upstream이 죽었으면 형제 버전으로 자동 재해석(rehome)해 body를 잇는다.
    sync의 계약 자체가 "upstream 따라 fresh 유지"라 자동이 맞다.
  - 단 재해석 결과가 같은 스킬인지 검증한다 — 스킬만 삭제된 경우 형제 스킬로
    하이재킹하면 body가 조용히 다른 도구가 되는 최악의 오염.
  - 이사한 항목에 boundary가 있으면 report가 flag만 한다(막지 않음) —
    새 버전에서 그 boundary가 여전히 유효한지는 사람이 본다.
  - 완전 증발이면 엔트리·overlay를 보존한 채 유실로 보고한다
    ("떨어져도 개인화는 남는다"를 유실 상황에서도 지킨다).

owned(upstream 없음)·linked(외부 실행)는 sync 대상이 아니다 — 손대지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter

from pouch.catalog.importer import import_vendored_skill
from pouch.catalog.model import Ownership, ToolEntry
from pouch.catalog.rehome import rehome_upstream
from pouch.catalog.store import CatalogStore


@dataclass(frozen=True)
class RehomedEntry:
    """버전 이사로 upstream이 바뀐 항목."""

    entry: ToolEntry
    old_upstream: str

    @property
    def needs_boundary_check(self) -> bool:
        """boundary가 걸린 채 이사했다 — 새 버전에서 유효성 확인 요망(막지 않음)."""
        return bool(self.entry.overlay and self.entry.overlay.boundaries)


@dataclass(frozen=True)
class MissingUpstream:
    """upstream이 완전히 증발한 항목 — body 유실, 엔트리·overlay는 생존."""

    entry_id: str
    upstream: str


@dataclass(frozen=True)
class SyncReport:
    """sync_all의 결과 — 제자리 갱신 / 이사 / 유실을 구분해 보고한다."""

    synced: tuple[ToolEntry, ...] = ()
    rehomed: tuple[RehomedEntry, ...] = ()
    missing: tuple[MissingUpstream, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.synced or self.rehomed or self.missing)


def sync_entry(store: CatalogStore, entry_id: str, *, synced_at: str) -> ToolEntry:
    """vendored 항목 하나를 upstream에서 재방문해 갱신한다.

    upstream이 죽었으면 형제 버전으로 재해석을 시도하고(같은 스킬일 때만),
    그래도 못 찾으면 FileNotFoundError를 그대로 올린다(조용히 삼키지 않음).
    vendored가 아니면 ValueError.
    """
    entry = store.get(entry_id)
    if entry is None:
        raise ValueError(f"카탈로그에 '{entry_id}' 항목이 없습니다.")
    if entry.ownership is not Ownership.VENDORED:
        raise ValueError(
            f"'{entry_id}'는 {entry.ownership.value}입니다. sync는 vendored만 대상으로 합니다."
        )
    if not entry.upstream:
        raise ValueError(f"'{entry_id}'에 upstream이 없어 sync할 수 없습니다.")

    upstream_path = Path(entry.upstream)
    if not upstream_path.exists():
        rehomed = rehome_upstream(entry.upstream)
        if rehomed is None or not _is_same_skill(rehomed, entry_id):
            raise FileNotFoundError(
                f"'{entry_id}'의 upstream이 사라졌습니다: {entry.upstream}"
            )
        upstream_path = rehomed

    # import_vendored_skill이 기존 overlay·tags를 보존하며 metadata를 다시 읽는다.
    # upstream엔 (재해석됐다면 새) 실제 경로를 기록한다.
    return import_vendored_skill(
        upstream_path,
        store,
        upstream=str(upstream_path),
        synced_at=synced_at,
        source=entry.source,
    )


def sync_all(store: CatalogStore, *, synced_at: str) -> SyncReport:
    """모든 vendored 항목을 sync한다. owned·linked는 건너뛴다.

    유실 하나가 전체를 인질로 잡지 않는다 — 항목별로 격리해 리포트로 모은다.
    """
    synced: list[ToolEntry] = []
    rehomed: list[RehomedEntry] = []
    missing: list[MissingUpstream] = []
    for entry in store.search(ownership=Ownership.VENDORED):
        old_upstream = entry.upstream or ""
        try:
            result = sync_entry(store, entry.id, synced_at=synced_at)
        except FileNotFoundError:
            missing.append(MissingUpstream(entry_id=entry.id, upstream=old_upstream))
            continue
        if result.upstream != old_upstream:
            rehomed.append(RehomedEntry(entry=result, old_upstream=old_upstream))
        else:
            synced.append(result)
    return SyncReport(synced=tuple(synced), rehomed=tuple(rehomed), missing=tuple(missing))


def moved_component(old: str, new: str) -> tuple[str, str]:
    """두 경로에서 처음 달라지는 컴포넌트 쌍 — 보고용("1.0.0 → 1.1.0")."""
    for old_part, new_part in zip(Path(old).parts, Path(new).parts):
        if old_part != new_part:
            return old_part, new_part
    return old, new


def _is_same_skill(path: Path, entry_id: str) -> bool:
    """재해석된 경로가 정말 같은 스킬인지 frontmatter name으로 검증한다."""
    try:
        return frontmatter.load(path).metadata.get("name") == entry_id
    except Exception:  # noqa: BLE001 — 못 읽으면 같다고 볼 근거가 없다
        return False
