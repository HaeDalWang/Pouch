"""세트 적용 — 출처에서 가져와 창고를 채우고, 고른 것만 연장통에 올린다.

세트는 가리키기만 한다: 가져오기는 기존 카탈로그 importer, 표면 올리기는
기존 install_entry를 그대로 탄다. 새 설치 메커니즘이 없다(선곡표 원칙).

항목 하나가 깨져도(출처 증발, 없는 id) 나머지는 계속 간다 — 건너뛴 것은
이유와 함께 보고한다(인질 금지, plugin import와 같은 정신).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pouch.catalog.commands import classify_source, find_plugin_roots
from pouch.catalog.importer import (
    import_hooks,
    import_mcp_servers,
    import_plugin,
    import_vendored_skill,
)
from pouch.catalog.install import install_entry
from pouch.catalog.model import SURFACE_PLUGIN, ToolEntry
from pouch.catalog.store import CatalogStore
from pouch.sets.model import StarterSet


@dataclass(frozen=True)
class SetApplyReport:
    """세트 적용 결과 — 담은 수, 올린 것, 건너뛴 것(이유 포함)."""

    imported: int
    installed: tuple[str, ...]
    skipped: tuple[str, ...]


def _import_source(
    source: Path, store: CatalogStore, *, synced_at: str
) -> list[ToolEntry]:
    """출처 하나를 종류 판별해 카탈로그에 들인다(기존 importer 위임)."""
    try:
        kind = classify_source(source)
    except ValueError:
        # 중첩 구조(<플러그인>/<버전>/…)면 안쪽에서 플러그인 루트를 찾는다.
        roots = find_plugin_roots(source) if source.is_dir() else []
        if len(roots) != 1:
            raise
        source, kind = roots[0], "plugin"

    if kind == "plugin":
        return list(
            import_plugin(source, store, synced_at=synced_at, source="set").entries
        )
    if kind == "mcp":
        return import_mcp_servers(source, store, source="set")
    if kind == "hooks":
        return import_hooks(source, store, source="set")
    return [
        import_vendored_skill(
            source if source.is_file() else source / "SKILL.md",
            store, upstream=str(source), synced_at=synced_at, source="set",
        )
    ]


def apply_set(
    starter: StarterSet,
    store: CatalogStore,
    *,
    skills_dir: Path,
    mcp_config_path: Path,
    settings_path: Path | None = None,
    state_path: Path | None = None,
    synced_at: str,
) -> SetApplyReport:
    """세트의 항목들을 가져오고(창고), install 목록만 표면(연장통)에 올린다."""
    imported = 0
    installed: list[str] = []
    skipped: list[str] = []

    for item in starter.items:
        source = Path(item.source).expanduser()
        if not source.exists():
            skipped.append(f"출처가 없어 건너뜀: {source}")
            continue
        try:
            entries = _import_source(source, store, synced_at=synced_at)
        except (ValueError, OSError) as exc:
            skipped.append(f"가져오기 실패({source}): {exc}")
            continue
        imported += len(entries)

        for entry_id in item.install:
            entry = store.get(entry_id)
            if entry is None:
                skipped.append(f"'{entry_id}'가 출처에 없어 못 올림")
                continue
            if entry.surface == SURFACE_PLUGIN:
                skipped.append(f"'{entry_id}'는 플러그인이 표면을 관리해 관측만")
                continue
            try:
                install_entry(
                    entry, skills_dir=skills_dir, mcp_config_path=mcp_config_path,
                    settings_path=settings_path, state_path=state_path,
                )
            except (ValueError, FileNotFoundError) as exc:
                skipped.append(f"'{entry_id}' 설치 실패: {exc}")
                continue
            installed.append(entry_id)

    return SetApplyReport(
        imported=imported, installed=tuple(installed), skipped=tuple(skipped)
    )
