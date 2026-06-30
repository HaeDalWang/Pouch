"""init 연결 계약 검증 — 역할·스택 → 카탈로그 추천 → 설치.

pouch = 개인 사서. "물어보고 나한테 맞는 것만 담는다"의 마지막 고리다.
역할·스택에서 관심 토큰을 뽑고, 그 토큰이 엔트리(태그·id·title)에 닿으면 추천한다.

  ① 스택 토큰이 엔트리 태그/id에 토큰 단위로 닿으면 추천한다 (aws → aws-iam, aws-cdk)
  ② 토큰 매칭은 substring이 아니라 토큰 단위다 (go가 google에 안 걸린다)
  ③ 안 닿으면 추천하지 않는다 (헛 추천 없음)
  ④ 결과는 중복 없이 id 정렬 — 결정적
  ⑤ 추천 → 설치가 이어진다 (vendored=upstream 재읽기, linked=MCP 등록)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pouch.catalog.model import ToolEntry, ToolKind
from pouch.catalog.recommend import (
    install_recommended,
    interest_tokens,
    recommend,
)
from pouch.init.profile import InitAnswers


def _vendored(id: str, *, tags: tuple[str, ...], upstream: str) -> ToolEntry:
    return ToolEntry.vendored(
        id=id, kind=ToolKind.SKILL, source="aws", title=id,
        description="", upstream=upstream, synced_at="2026-06-30", tags=tags,
    )


def _linked(id: str, *, tags: tuple[str, ...]) -> ToolEntry:
    return ToolEntry.linked(
        id=id, kind=ToolKind.MCP, source="aws", title=id, description="",
        recipe={"command": "uvx", "args": []}, tags=tags,
    )


@pytest.fixture
def upstream_skills(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name in ("aws-iam", "aws-cdk", "go-patterns"):
        sdir = tmp_path / "up" / name
        sdir.mkdir(parents=True)
        p = sdir / "SKILL.md"
        p.write_text(f"---\nname: {name}\ndescription: d\n---\n\n# {name}\n\n{name} 본문\n", encoding="utf-8")
        paths[name] = p
    return paths


@pytest.fixture
def entries(upstream_skills: dict[str, Path]) -> list[ToolEntry]:
    return [
        _vendored("aws-iam", tags=("vendor:aws",), upstream=str(upstream_skills["aws-iam"])),
        _vendored("aws-cdk", tags=("vendor:aws",), upstream=str(upstream_skills["aws-cdk"])),
        _vendored("go-patterns", tags=("lang:go",), upstream=str(upstream_skills["go-patterns"])),
        _linked("aws-mcp", tags=("vendor:aws",)),
    ]


def test_interest_tokens_from_role_and_stacks() -> None:
    answers = InitAnswers(role="AWS engineer", stacks=("python", "go"), work_style=None)
    tokens = interest_tokens(answers)
    assert "aws" in tokens
    assert "python" in tokens
    assert "go" in tokens
    # 일반 직군 단어는 노이즈라 토큰에서 빠진다
    assert "engineer" not in tokens


def test_contract1_stack_matches_by_tag_and_id(entries: list[ToolEntry]) -> None:
    answers = InitAnswers(role="backend", stacks=("aws",), work_style=None)
    recommended = recommend(entries, answers)
    ids = {e.id for e in recommended}
    # aws 토큰이 vendor:aws 태그와 aws-* id에 닿는다
    assert "aws-iam" in ids
    assert "aws-cdk" in ids
    assert "aws-mcp" in ids
    # go-patterns는 aws와 무관
    assert "go-patterns" not in ids


def test_contract2_token_match_not_substring(entries: list[ToolEntry]) -> None:
    # "go" 스택은 go-patterns에 닿지만, "google" 같은 단어엔 안 걸려야 한다.
    answers = InitAnswers(role="dev", stacks=("go",), work_style=None)
    recommended = recommend(entries, answers)
    ids = {e.id for e in recommended}
    assert "go-patterns" in ids
    assert "aws-iam" not in ids


def test_contract3_no_match_no_recommend(entries: list[ToolEntry]) -> None:
    answers = InitAnswers(role="dev", stacks=("haskell",), work_style=None)
    assert recommend(entries, answers) == []


def test_contract4_deterministic_sorted_unique(entries: list[ToolEntry]) -> None:
    answers = InitAnswers(role="aws dev", stacks=("aws",), work_style=None)
    recommended = recommend(entries, answers)
    ids = [e.id for e in recommended]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_contract5_recommend_then_install(entries: list[ToolEntry], tmp_path: Path) -> None:
    answers = InitAnswers(role="backend", stacks=("aws",), work_style=None)
    recommended = recommend(entries, answers)

    skills_dir = tmp_path / "skills"
    mcp_config = tmp_path / ".mcp.json"
    installed = install_recommended(recommended, skills_dir=skills_dir, mcp_config_path=mcp_config)

    # vendored 스킬은 SKILL.md로, linked는 mcp 설정으로
    assert (skills_dir / "aws-iam" / "SKILL.md").exists()
    assert (skills_dir / "aws-cdk" / "SKILL.md").exists()
    cfg = json.loads(mcp_config.read_text(encoding="utf-8"))
    assert "aws-mcp" in cfg["mcpServers"]
    assert len(installed) == len(recommended)
