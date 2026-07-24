"""저장소 색인 — Phase 4.8 조각 ②. sweep의 원격판.

핵심 발상: **등록한 저장소의 클론도 도구통이다.** 어디를 어떻게 훑을지는 이미
sweep이 안다(layout별 후보 뽑기·기존 importer·인질 금지 보고) — 여기서는 클론을
ToolboxHost 하나로 감싸 그 기계에 태울 뿐, 파싱 코드를 새로 짓지 않는다.

색인이 앉는 자리는 저장소별 티어(`~/.pouch/repo-index/<이름>/`)다. 로컬 훑기의
대기실(`sources/`)과 섞지 않는 이유: 정체가 `<저장소>/<도구>`인데 대기실 장부는
평면이라 "/"를 못 담는다 — 세트 레지스트리(`registry/sets/<author>/`)처럼 **자리가
저장소 이름을 답하게** 한다(출처 표시가 공짜로 따라온다, 조각 ③의 재료).

색인은 파생물이다. 클론이 유일한 진실이라 재색인은 **지우고 다시 만든다** —
upstream에서 사라진 도구가 색인에 유령으로 남지 않는다(개인화는 여기 산 적이
없어 지워도 잃는 게 없다).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from pouch.catalog.model import ToolKind
from pouch.catalog.store import CatalogStore
from pouch.catalog.sweep import SweepReport, sweep_toolboxes
from pouch.hosts.base import (
    LAYOUT_DOCS_FLAT,
    LAYOUT_FILE,
    LAYOUT_SKILLS_ROOT,
    Toolbox,
)


@dataclass(frozen=True)
class RepoToolbox:
    """클론 하나를 도구통 호스트로 — sweep이 아는 계약(ToolboxHost)에 맞춘다.

    아는 배치만 답한다(ROADMAP 4.8 ② 락): skills/·agents/·commands/·rules/·
    .mcp.json. ClaudeAdapter의 자리 목록과 같은 꼴이되 플러그인 캐시는 없다
    (저장소는 하네스가 아니라 파일 묶음이다). 모르는 구조는 자리 목록에 없으니
    자연히 안 잡힌다 — 못 찾음은 흠이 아니다.
    """

    name: str
    clone_dir: Path

    @property
    def display_name(self) -> str:
        return f"저장소 {self.name}"

    def toolbox_paths(self) -> tuple[Toolbox, ...]:
        root = self.clone_dir
        return (
            Toolbox(path=root / "skills", layout=LAYOUT_SKILLS_ROOT),
            Toolbox(path=root / ".mcp.json", layout=LAYOUT_FILE),
            Toolbox(path=root / "hooks.json", layout=LAYOUT_FILE),
            Toolbox(path=root / "agents", layout=LAYOUT_DOCS_FLAT, kind=ToolKind.AGENT),
            Toolbox(
                path=root / "commands", layout=LAYOUT_DOCS_FLAT, kind=ToolKind.COMMAND
            ),
            Toolbox(path=root / "rules", layout=LAYOUT_DOCS_FLAT, kind=ToolKind.RULE),
        )


def index_repo(
    name: str, clone_dir: Path, *, index_dir: Path, synced_at: str
) -> SweepReport:
    """클론을 훑어 색인 티어를 새로 만든다. 카탈로그·표면은 안 건드린다.

    가리키기만: 색인 엔트리는 vendored 참조(upstream=클론 안 경로)라 본문을
    복사하지 않고, 진입·설치는 기존 관문이 그대로 지킨다.
    """
    if index_dir.exists():
        shutil.rmtree(index_dir)  # 파생물 재생성 — 유령 방지
    return sweep_toolboxes(
        source_store=CatalogStore(catalog_dir=index_dir),
        hosts=[RepoToolbox(name=name, clone_dir=clone_dir)],
        synced_at=synced_at,
    )


def indexed_count(index_dir: Path) -> int:
    """색인에 앉은 도구 수 — repo list가 보여줄 한 칸."""
    if not index_dir.exists():
        return 0
    return sum(1 for _ in CatalogStore(catalog_dir=index_dir).list())
