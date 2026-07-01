"""설치 계약 검증 — ownership이 설치 메커니즘을 가른다.

  owned    : body가 내 것 → catalog의 body를 파일로 쓴다
  vendored : body 미보유 → upstream에서 '다시 읽어' 배치한다 (catalog엔 본문 없음)
  linked   : 파일이 아님 → MCP 설정에 recipe 등록 (백업 동반, 복구 가능)

핵심 비대칭:
  ① owned 설치 → SKILL.md에 catalog body가 그대로 들어간다
  ② vendored 설치 → upstream을 다시 읽어 배치 (upstream 없으면 조용히 삼키지 않고 실패)
  ③ linked 설치 → 파일을 만들지 않고 mcpServers에 recipe를 등록한다 (멱등, 백업)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pouch.catalog.install import (
    install_entry,
    install_skill_file,
    is_mcp_registered,
    register_mcp,
    with_mcp_registered,
)
from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore

_OWNED_BODY = "# 내 워크플로\n\nINSTALLED_OWNED_BODY\n\n절차..."


def _owned() -> ToolEntry:
    return ToolEntry.owned(
        id="my-wf", kind=ToolKind.SKILL, source="me",
        title="내 워크플로", description="owned", body=_OWNED_BODY,
    )


def _linked() -> ToolEntry:
    return ToolEntry.linked(
        id="aws-mcp", kind=ToolKind.MCP, source="aws", title="aws-mcp",
        description="linked",
        recipe={"command": "uvx", "args": ["mcp-proxy-for-aws@latest", "https://x.us-east-1.api.aws/mcp"]},
        region="us-east-1",
    )


@pytest.fixture
def upstream_skill(tmp_path: Path) -> Path:
    sdir = tmp_path / "upstream" / "aws-iam"
    sdir.mkdir(parents=True)
    path = sdir / "SKILL.md"
    path.write_text(
        "---\nname: aws-iam\ndescription: IAM 절차\n---\n\n# AWS IAM\n\nUPSTREAM_FRESH_BODY\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def vendored(upstream_skill: Path, tmp_path: Path) -> ToolEntry:
    from pouch.catalog.importer import import_vendored_skill

    store = CatalogStore(catalog_dir=tmp_path / "catalog")
    return import_vendored_skill(
        upstream_skill, store, upstream=str(upstream_skill), synced_at="2026-06-30"
    )


def test_contract1_owned_writes_catalog_body(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"

    path = install_skill_file(_owned(), skills_dir=skills_dir)

    assert path == skills_dir / "my-wf" / "SKILL.md"
    assert "INSTALLED_OWNED_BODY" in path.read_text(encoding="utf-8")


def test_contract2_vendored_reads_upstream(vendored: ToolEntry, tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"

    path = install_skill_file(vendored, skills_dir=skills_dir)

    # catalog엔 body가 없으니 upstream을 다시 읽어야만 본문이 들어간다
    assert vendored.body is None
    assert "UPSTREAM_FRESH_BODY" in path.read_text(encoding="utf-8")


def test_contract2_vendored_missing_upstream_fails(
    vendored: ToolEntry, upstream_skill: Path, tmp_path: Path
) -> None:
    upstream_skill.unlink()
    with pytest.raises(FileNotFoundError):
        install_skill_file(vendored, skills_dir=tmp_path / "skills")


def test_contract3_linked_registers_recipe_no_file(tmp_path: Path) -> None:
    config = {}
    updated = with_mcp_registered(config, _linked())

    servers = updated["mcpServers"]
    assert servers["aws-mcp"]["command"] == "uvx"
    assert "mcp-proxy-for-aws@latest" in servers["aws-mcp"]["args"]
    # 원본 불변(immutability)
    assert config == {}


def test_with_mcp_registered_is_idempotent() -> None:
    once = with_mcp_registered({}, _linked())
    twice = with_mcp_registered(once, _linked())
    assert once == twice
    assert is_mcp_registered(twice, "aws-mcp")


def test_register_mcp_writes_with_backup(tmp_path: Path) -> None:
    config_path = tmp_path / ".mcp.json"
    config_path.write_text(json.dumps({"mcpServers": {"existing": {"command": "x"}}}), encoding="utf-8")

    backup = register_mcp(config_path, _linked())

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "aws-mcp" in data["mcpServers"]
    assert "existing" in data["mcpServers"]  # 기존 서버 보존
    assert backup is not None and backup.exists()


def test_install_entry_dispatches_by_ownership(
    vendored: ToolEntry, tmp_path: Path
) -> None:
    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"

    owned_path = install_entry(_owned(), skills_dir=skills_dir, mcp_config_path=mcp_config)
    vendored_path = install_entry(vendored, skills_dir=skills_dir, mcp_config_path=mcp_config)
    linked_result = install_entry(_linked(), skills_dir=skills_dir, mcp_config_path=mcp_config)

    assert owned_path == skills_dir / "my-wf" / "SKILL.md"
    assert vendored_path == skills_dir / "aws-iam" / "SKILL.md"
    # linked는 파일이 아니라 설정 경로를 돌려준다
    assert linked_result == mcp_config
    assert is_mcp_registered(json.loads(mcp_config.read_text(encoding="utf-8")), "aws-mcp")


def test_install_entry_records_active_state(tmp_path: Path) -> None:
    # 설치는 활성 표면에 올리는 지점 = state.json에 installed_at·active로 남는다.
    # evolve가 볼 데이터를 여기서 심는다(안 남으면 evolve는 영원히 장님).
    from pouch.evolution.state import active_entries

    state = tmp_path / "state.json"
    install_entry(
        _owned(), skills_dir=tmp_path / "skills", mcp_config_path=tmp_path / ".mcp.json",
        now="2026-07-01T00:00:00", state_path=state,
    )

    assert active_entries(state_path=state) == {"my-wf": "2026-07-01T00:00:00"}


def test_install_entry_reattach_refreshes_state(tmp_path: Path) -> None:
    # 재부착 = installed_at 갱신(never-used 시계 리셋). drop 후 재설치 경로.
    from pouch.evolution.state import active_entries, mark_dropped

    state = tmp_path / "state.json"
    skills_dir = tmp_path / "skills"
    mcp = tmp_path / ".mcp.json"
    install_entry(_owned(), skills_dir=skills_dir, mcp_config_path=mcp,
                  now="2026-06-01T00:00:00", state_path=state)
    mark_dropped("my-wf", state_path=state)

    install_entry(_owned(), skills_dir=skills_dir, mcp_config_path=mcp,
                  now="2026-07-01T00:00:00", state_path=state)

    assert active_entries(state_path=state) == {"my-wf": "2026-07-01T00:00:00"}
