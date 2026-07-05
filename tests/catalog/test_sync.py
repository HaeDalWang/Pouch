"""sync 계약 검증 — vendored upstream 갱신을 카탈로그에 반영한다.

sync는 import의 역방향이 아니라 '재방문'이다. 카탈로그에 이미 있는 vendored
엔트리들의 upstream을 다시 읽어 최신 metadata로 맞춘다:
  ① vendored만 sync한다 (owned=upstream 없음, linked=외부 — 둘 다 건너뜀)
  ② upstream이 바뀌면 metadata(description 등)가 갱신된다
  ③ overlay는 보존된다 (개인화는 upstream 갱신에 안 쓸려나감)
  ④ synced_at이 갱신된다
  ⑤ upstream 파일이 사라졌으면 조용히 삼키지 않고 결과로 보고한다

버전 이사(rehome) 계약 — "body는 자동 이사, boundary는 flag만" 층 구분:
  R① body가 새 경로를 가리킨다 (fresh 유지)
  R② overlay가 이사 후에도 살아있다 (prod-gate 안 죽음 — evolve 멱등성의 sync판)
  R③ 완전 증발 시 body 유실을 보고하되 엔트리·overlay는 보존한다
     ("떨어져도 개인화는 남는다"를 유실 상황에서도 지킴) + 다른 항목 sync는 계속
  R④ 이사한 항목에 boundary가 있으면 report가 확인 요망을 flag한다 (막지 않음)
  R⑤ 이사 대상은 같은 스킬이어야 한다 — 스킬만 삭제된 경우 형제 스킬로
     하이재킹하지 않고 유실로 보고한다
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pouch.catalog.importer import apply_overlay, import_vendored_skill
from pouch.catalog.model import Overlay, Ownership, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.catalog.sync import sync_all, sync_entry


def _skill_md(name: str, description: str, body: str = "본문 절차...") -> str:
    return f"""---
name: {name}
description: {description}
version: 1
---

# {name}

{body}
"""


@pytest.fixture
def upstream_skill(tmp_path: Path) -> Path:
    sdir = tmp_path / "upstream" / "aws-iam"
    sdir.mkdir(parents=True)
    path = sdir / "SKILL.md"
    path.write_text(_skill_md("aws-iam", "원래 설명"), encoding="utf-8")
    return path


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(catalog_dir=tmp_path / "catalog")


def test_contract2_metadata_refreshed_on_upstream_change(
    upstream_skill: Path, store: CatalogStore
) -> None:
    # Arrange — import 후 upstream이 갱신됨
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    upstream_skill.write_text(_skill_md("aws-iam", "갱신된 설명"), encoding="utf-8")

    # Act
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")

    # Assert
    assert result.description == "갱신된 설명"
    assert store.get("aws-iam").description == "갱신된 설명"


def test_contract3_overlay_preserved(upstream_skill: Path, store: CatalogStore) -> None:
    # Arrange
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    apply_overlay(store, "aws-iam", Overlay(boundaries=("prod-gate",), notes="내 메모"))
    upstream_skill.write_text(_skill_md("aws-iam", "갱신된 설명"), encoding="utf-8")

    # Act
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")

    # Assert — upstream 갱신돼도 내 overlay는 그대로
    assert result.overlay.boundaries == ("prod-gate",)
    assert result.overlay.notes == "내 메모"


def test_contract4_synced_at_updated(upstream_skill: Path, store: CatalogStore) -> None:
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")
    assert result.synced_at == "2026-07-05"


def test_contract5_missing_upstream_reported_not_swallowed(
    upstream_skill: Path, store: CatalogStore
) -> None:
    # Arrange — import 후 upstream이 사라짐
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    upstream_skill.unlink()

    # Act & Assert — 조용히 삼키지 않고 명확히 실패
    with pytest.raises(FileNotFoundError):
        sync_entry(store, "aws-iam", synced_at="2026-07-05")


def test_contract1_sync_all_skips_owned_and_linked(
    upstream_skill: Path, store: CatalogStore
) -> None:
    # Arrange — vendored 1 + owned 1 + linked 1
    import_vendored_skill(upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30")
    store.save(
        ToolEntry.owned(
            id="my-wf", kind=ToolKind.SKILL, source="me", title="내 워크플로",
            description="owned", body="내 본문",
        )
    )
    store.save(
        ToolEntry.linked(
            id="aws-mcp", kind=ToolKind.MCP, source="aws", title="aws-mcp",
            description="linked", recipe={"command": "uvx", "args": []},
        )
    )
    upstream_skill.write_text(_skill_md("aws-iam", "갱신된 설명"), encoding="utf-8")

    # Act
    report = sync_all(store, synced_at="2026-07-05")

    # Assert — vendored만 sync. owned·linked는 손도 안 댐.
    assert [e.id for e in report.synced] == ["aws-iam"]
    assert not report.rehomed and not report.missing
    assert store.get("my-wf").body == "내 본문"
    assert store.get("aws-mcp").ownership is Ownership.LINKED


def test_sync_entry_rejects_non_vendored(store: CatalogStore) -> None:
    store.save(
        ToolEntry.owned(
            id="my-wf", kind=ToolKind.SKILL, source="me", title="t",
            description="d", body="b",
        )
    )
    with pytest.raises(ValueError):
        sync_entry(store, "my-wf", synced_at="2026-07-05")


# ── 버전 이사(rehome) — "body는 자동 이사, boundary는 flag만" ─────────────


def _plugin_skill(base: Path, version: str, description: str, name: str = "aws-iam") -> Path:
    """플러그인 캐시 모양(<mkt>/<plug>/<version>/skills/...)의 스킬을 만든다."""
    path = base / "cache" / "mkt" / "plug" / version / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(_skill_md(name, description), encoding="utf-8")
    return path


def _version_dir(skill_path: Path) -> Path:
    return skill_path.parents[2]  # SKILL.md → <skill>/ → skills/ → <version>/


def test_rehome1_body_relinks_to_new_version(tmp_path: Path, store: CatalogStore) -> None:
    # Arrange — 1.0.0으로 import한 뒤, 플러그인 업데이트(1.0.0 삭제, 1.1.0 등장)
    old = _plugin_skill(tmp_path, "1.0.0", "원래 설명")
    import_vendored_skill(old, store, upstream=str(old), synced_at="2026-06-30")
    new = _plugin_skill(tmp_path, "1.1.0", "갱신된 설명")
    shutil.rmtree(_version_dir(old))

    # Act
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")

    # Assert — body가 새 경로를 가리키고 fresh가 유지된다
    assert result.upstream == str(new)
    assert result.description == "갱신된 설명"
    assert store.get("aws-iam").upstream == str(new)


def test_rehome2_overlay_survives_move(tmp_path: Path, store: CatalogStore) -> None:
    # Arrange
    old = _plugin_skill(tmp_path, "1.0.0", "원래 설명")
    import_vendored_skill(old, store, upstream=str(old), synced_at="2026-06-30")
    apply_overlay(store, "aws-iam", Overlay(boundaries=("prod-gate",), notes="내 메모"))
    _plugin_skill(tmp_path, "1.1.0", "갱신된 설명")
    shutil.rmtree(_version_dir(old))

    # Act
    result = sync_entry(store, "aws-iam", synced_at="2026-07-05")

    # Assert — 이사해도 개인화(prod-gate)는 안 죽는다
    assert result.overlay.boundaries == ("prod-gate",)
    assert result.overlay.notes == "내 메모"


def test_rehome3_evaporated_keeps_entry_and_overlay_and_continues(
    tmp_path: Path, store: CatalogStore
) -> None:
    # Arrange — 증발 1개(형제 버전 없음) + 건강한 vendored 1개
    gone = _plugin_skill(tmp_path, "1.0.0", "증발할 스킬")
    import_vendored_skill(gone, store, upstream=str(gone), synced_at="2026-06-30")
    apply_overlay(store, "aws-iam", Overlay(boundaries=("prod-gate",)))
    healthy = _plugin_skill(tmp_path, "9.9.9", "건강한 스킬", name="aws-s3")
    import_vendored_skill(healthy, store, upstream=str(healthy), synced_at="2026-06-30")
    shutil.rmtree(tmp_path / "cache" / "mkt" / "plug" / "1.0.0")

    # Act — 인질 없음: 하나가 증발해도 전체 sync는 계속된다
    report = sync_all(store, synced_at="2026-07-05")

    # Assert — 유실은 보고되고, 엔트리·overlay는 살아있고, 나머지는 sync됐다
    assert [m.entry_id for m in report.missing] == ["aws-iam"]
    survivor = store.get("aws-iam")
    assert survivor is not None
    assert survivor.overlay.boundaries == ("prod-gate",)
    assert [e.id for e in report.synced] == ["aws-s3"]


def test_rehome4_report_flags_boundary_check_on_move(
    tmp_path: Path, store: CatalogStore
) -> None:
    # Arrange — boundary 있는 스킬과 없는 스킬이 함께 이사한다
    old_a = _plugin_skill(tmp_path, "1.0.0", "설명 A")
    old_b = _plugin_skill(tmp_path, "1.0.0", "설명 B", name="aws-s3")
    import_vendored_skill(old_a, store, upstream=str(old_a), synced_at="2026-06-30")
    import_vendored_skill(old_b, store, upstream=str(old_b), synced_at="2026-06-30")
    apply_overlay(store, "aws-iam", Overlay(boundaries=("prod-gate",)))
    _plugin_skill(tmp_path, "1.1.0", "설명 A")
    _plugin_skill(tmp_path, "1.1.0", "설명 B", name="aws-s3")
    shutil.rmtree(tmp_path / "cache" / "mkt" / "plug" / "1.0.0")

    # Act
    report = sync_all(store, synced_at="2026-07-05")

    # Assert — flag만(막지 않음): boundary 있는 이사만 확인 요망
    flags = {r.entry.id: r.needs_boundary_check for r in report.rehomed}
    assert flags == {"aws-iam": True, "aws-s3": False}


def test_rehome5_no_hijack_when_skill_removed_in_place(
    tmp_path: Path, store: CatalogStore
) -> None:
    # Arrange — 버전 디렉토리는 그대로인데 스킬만 삭제됨(형제 스킬은 존재)
    target = _plugin_skill(tmp_path, "1.0.0", "삭제될 스킬")
    _plugin_skill(tmp_path, "1.0.0", "형제 스킬", name="aws-s3")
    import_vendored_skill(target, store, upstream=str(target), synced_at="2026-06-30")
    shutil.rmtree(target.parent)

    # Act
    report = sync_all(store, synced_at="2026-07-05")

    # Assert — 형제 스킬로 하이재킹하지 않고 유실로 보고한다
    assert [m.entry_id for m in report.missing] == ["aws-iam"]
    assert store.get("aws-iam").upstream == str(target)  # 엉뚱한 곳을 가리키지 않음
