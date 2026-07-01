"""uninstall/reattach 계약 검증 — install.py의 거울상. "떨어진다 ≠ 삭제된다".

핵심 초석: **uninstall은 카탈로그를 절대 안 만진다.** 활성 표면(SKILL.md /
mcpServers)만 걷어내고, 엔트리+overlay는 store에 살아남는다. 재부착은
기존 install_entry 재실행. 이게 "prod-gate 경계는 도구가 떨어져도 안 죽는다"의
구조적 보장 — overlay를 '살려두는' 게 아니라 애초에 죽을 자리에 없다.

  ① uninstall skill → SKILL.md 제거, 카탈로그 엔트리+overlay 그대로
  ② uninstall linked → mcpServers에서만 제거(다른 서버 보존, 백업)
  ③ 멱등 — 없는 걸 uninstall해도 안 죽는다
  ④ ★초석★ drop → 카탈로그 overlay 생존 → 재부착 → 표면 복귀
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch.catalog.install import install_entry, is_mcp_registered
from pouch.catalog.model import Overlay, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore
from pouch.catalog.uninstall import (
    uninstall_entry,
    uninstall_skill_file,
    unregister_mcp,
    with_mcp_unregistered,
)


def _owned(id: str = "my-wf") -> ToolEntry:
    return ToolEntry.owned(
        id=id, kind=ToolKind.SKILL, source="me",
        title="내 워크플로", description="d", body="# body\n\n절차",
    )


def _linked(id: str = "aws-mcp") -> ToolEntry:
    return ToolEntry.linked(
        id=id, kind=ToolKind.MCP, source="aws", title=id, description="d",
        recipe={"command": "uvx", "args": ["x"]},
    )


def test_contract1_uninstall_skill_removes_file(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    path = install_entry(_owned(), skills_dir=skills_dir, mcp_config_path=tmp_path / ".mcp.json")
    assert path.exists()

    removed = uninstall_skill_file("my-wf", skills_dir=skills_dir)

    assert removed is True
    assert not path.exists()
    assert not path.parent.exists()  # <id>/ 디렉토리째 정리


def test_contract2_unregister_linked_preserves_others(tmp_path: Path) -> None:
    config = {"mcpServers": {"aws-mcp": {"command": "uvx"}, "keep-me": {"command": "x"}}}

    updated = with_mcp_unregistered(config, "aws-mcp")

    assert "aws-mcp" not in updated["mcpServers"]
    assert "keep-me" in updated["mcpServers"]  # 다른 서버 보존
    assert config["mcpServers"]["aws-mcp"]  # 원본 불변


def test_contract2_unregister_writes_with_backup(tmp_path: Path) -> None:
    config_path = tmp_path / ".mcp.json"
    install_entry(_linked(), skills_dir=tmp_path / "skills", mcp_config_path=config_path)

    backup = unregister_mcp(config_path, "aws-mcp")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert not is_mcp_registered(data, "aws-mcp")
    assert backup is not None and backup.exists()


def test_contract3_uninstall_is_idempotent(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    config_path = tmp_path / ".mcp.json"

    # 아무것도 설치 안 된 상태에서 uninstall → 안 죽고 False
    assert uninstall_skill_file("nope", skills_dir=skills_dir) is False
    assert with_mcp_unregistered({}, "nope") == {}
    # dispatch도 멱등
    uninstall_entry(_owned(), skills_dir=skills_dir, mcp_config_path=config_path)
    uninstall_entry(_owned(), skills_dir=skills_dir, mcp_config_path=config_path)


def test_contract4_cornerstone_overlay_survives_drop_and_reattach(tmp_path: Path) -> None:
    """★ drop → 카탈로그 overlay 생존 → 재부착 → 표면 복귀."""
    catalog_dir = tmp_path / "catalog"
    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"
    store = CatalogStore(catalog_dir=catalog_dir)

    # vendored 엔트리 + 내가 쌓은 prod-gate 경계(overlay)를 카탈로그에 저장
    upstream = tmp_path / "up" / "aws-iam" / "SKILL.md"
    upstream.parent.mkdir(parents=True)
    upstream.write_text("---\nname: aws-iam\ndescription: d\n---\n\n# IAM\n\n본문", encoding="utf-8")
    entry = ToolEntry.vendored(
        id="aws-iam", kind=ToolKind.SKILL, source="aws", title="aws-iam",
        description="d", upstream=str(upstream), synced_at="2026-07-01",
        overlay=Overlay(boundaries=("prod-gate",), notes="내 경계"),
    )
    store.save(entry)
    install_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config)

    # drop — 표면에서 내린다
    uninstall_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config)
    assert not (skills_dir / "aws-iam" / "SKILL.md").exists()  # 표면에서 사라짐

    # ★ 카탈로그 엔트리 + overlay는 살아있다 (prod-gate 경계 안 죽음)
    survived = store.get("aws-iam")
    assert survived is not None
    assert survived.overlay is not None
    assert survived.overlay.boundaries == ("prod-gate",)
    assert survived.overlay.notes == "내 경계"

    # 재부착 = install_entry 재실행 → 표면 복귀
    install_entry(store.get("aws-iam"), skills_dir=skills_dir, mcp_config_path=mcp_config)
    assert (skills_dir / "aws-iam" / "SKILL.md").exists()
