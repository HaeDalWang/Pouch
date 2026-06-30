"""추천 — 역할·스택에서 관심 토큰을 뽑아 카탈로그 항목과 잇는다.

pouch = 개인 사서. "물어보고 나한테 맞는 것만 담는다"의 마지막 고리다.
매칭은 substring이 아니라 토큰 단위다: 양쪽(관심사 / 엔트리)을 토큰 집합으로
쪼개 교집합이 있으면 추천한다. 그래야 "go"가 "google"에 헛걸리지 않는다.
"""

from __future__ import annotations

import re
from pathlib import Path

from pouch.catalog.install import install_entry
from pouch.catalog.model import ToolEntry
from pouch.init.profile import InitAnswers

# 토큰 경계: 영숫자가 아닌 것 전부(`-`, `:`, ` `, `_` …).
_TOKEN_RE = re.compile(r"[^a-z0-9]+")

# 역할에 흔히 섞이는 일반 직군 단어 — 관심 토큰에서 노이즈로 뺀다.
_NOISE_TOKENS = frozenset(
    {"engineer", "developer", "dev", "programmer", "senior", "junior", "lead"}
)


def _tokenize(text: str) -> set[str]:
    """문자열을 소문자 토큰 집합으로 쪼갠다. 빈 토큰은 버린다."""
    return {tok for tok in _TOKEN_RE.split(text.lower()) if tok}


def interest_tokens(answers: InitAnswers) -> set[str]:
    """역할·스택에서 관심 토큰을 뽑는다. 일반 직군 단어는 노이즈로 제외."""
    tokens = _tokenize(answers.role)
    for stack in answers.stacks:
        tokens |= _tokenize(stack)
    return tokens - _NOISE_TOKENS


def _entry_tokens(entry: ToolEntry) -> set[str]:
    """엔트리의 검색 가능한 토큰 — id·title·태그를 모두 쪼갠 집합."""
    tokens = _tokenize(entry.id) | _tokenize(entry.title)
    for tag in entry.tags:
        tokens |= _tokenize(tag)
    return tokens


def recommend(entries: list[ToolEntry], answers: InitAnswers) -> list[ToolEntry]:
    """관심 토큰이 엔트리 토큰과 겹치는 항목을 추천한다. id 정렬·중복 없음."""
    interests = interest_tokens(answers)
    matched = [e for e in entries if interests & _entry_tokens(e)]
    return sorted(matched, key=lambda e: e.id)


def install_recommended(
    recommended: list[ToolEntry], *, skills_dir: Path, mcp_config_path: Path
) -> list[Path]:
    """추천 항목을 ownership에 맞게 설치하고 결과 경로 목록을 반환한다."""
    return [
        install_entry(entry, skills_dir=skills_dir, mcp_config_path=mcp_config_path)
        for entry in recommended
    ]
