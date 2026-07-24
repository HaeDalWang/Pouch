"""pouch 저장소 경로 결정.

글로벌은 홈 아래 고정, 프로젝트는 작업 위치에서 위로 올라가며 탐지한다.
모든 메모리는 플랫 마크다운 파일이라 이 디렉토리를 그대로 백업(S3 sync 등)할 수 있다.
"""

from __future__ import annotations

import os
from pathlib import Path


def global_root() -> Path:
    """pouch 전역 루트. `POUCH_HOME` 환경변수로 오버라이드 가능(테스트/이전 용이)."""
    override = os.environ.get("POUCH_HOME")
    return Path(override).expanduser() if override else Path.home() / ".pouch"


def global_memory_dir() -> Path:
    """사용자 전역 메모리 디렉토리(`~/.pouch/memory/`)."""
    return global_root() / "memory"


def catalog_dir() -> Path:
    """도구 카탈로그 디렉토리(`~/.pouch/catalog/`).

    진입한 도구가 산다 — 실사용·install·세트로 카탈로그에 들어온 것. 목록·조언·
    추천이 보는 곳. 소스 스테이징(sources_dir)과 위치로 갈린다.
    """
    return global_root() / "catalog"


def project_catalog_dir(start: Path | None = None) -> Path | None:
    """현재 프로젝트의 카탈로그(`<repo>/.pouch/catalog/`). 프로젝트 밖이면 None.

    프로젝트별 주머니 — 전역 카탈로그(catalog_dir)의 프로젝트 스코프 짝. 그 repo에서만
    통하는 도구가 산다(멀티 클라이언트: 클라이언트 도구 vs 내부 도구 분리). memory가
    global/project 2계층인 것과 같은 확장이다. `.pouch/`라 로컬 전용·백업 제외.
    """
    root = find_project_root(start)
    return (root / ".pouch" / "catalog") if root else None


def sources_dir() -> Path:
    """소스 스테이징 디렉토리(`~/.pouch/sources/`) — 관문 (다)의 "가리키기" 자리.

    import한 번들이 담은 것을 카탈로그에 올리기 전 재워두는 곳. 목록·조언·추천은
    여기를 안 본다("아직 안 쓴 백과사전 페이지"). 사용자가 실제로 쓰면 promote가
    카탈로그로 진입시킨다. 카탈로그와 형제라 같은 CatalogStore로 다루되(디렉토리만
    다름) 위치가 곧 상태 구분이다(ownership이 필드로 관계를 가르는 것과 같은 정신).
    """
    return global_root() / "sources"


def sets_dir() -> Path:
    """사용자 시작 세트 디렉토리(`~/.pouch/sets/`).

    내장 세트와 같은 형식의 JSON을 여기 두면 함께 읽힌다(같은 이름은 사용자 우선).
    나중에 세트 공유(raft)가 이 형식을 그대로 주고받는다.
    """
    return global_root() / "sets"


def repos_dir() -> Path:
    """등록한 도구 저장소들의 클론 자리(`~/.pouch/repos/<이름>/`) — Phase 4.8.

    helm repo add의 pouch판. 여러 개가 이름으로 나란히 산다 — 단일 registry
    (registry_dir, 세트 전용)와 달리 낱개 도구들의 주소를 물어두는 곳. 별도 장부
    파일 없음: 클론 디렉토리와 git remote가 유일한 진실.
    """
    return global_root() / "repos"


def repo_index_root() -> Path:
    """저장소 색인 티어의 뿌리(`~/.pouch/repo-index/<이름>/`) — Phase 4.8 ②.

    클론(repos_dir)에서 파생된 도구 색인이 저장소별로 산다. 클론 안에 두지 않는
    이유: git 작업 트리를 더럽히지 않기 위해. 로컬 대기실(sources_dir)과 섞지 않는
    이유: 정체 `<저장소>/<도구>`의 저장소 칸을 자리가 답하게(레지스트리 패턴).
    """
    return global_root() / "repo-index"


def registry_dir() -> Path:
    """당겨온 세트가 사는 별도 티어(`~/.pouch/registry/`) — 팀 공유 레지스트리의 클론.

    raft의 받는 쪽(`pouch set pull`). git 레지스트리 repo를 여기 clone하고, 세트는
    `registry/sets/<author>/<name>.json`으로 산다. 내가 만든 `sets/`(sets_dir)와 안
    섞인다 — 이름 충돌 시 로컬(내 것)이 이기고, 재-pull은 이 티어만 멱등 갱신한다
    (개인 우선을 구조로 강제). 설계: docs/RAFT-DESIGN.md.
    """
    return global_root() / "registry"


def usage_log_path() -> Path:
    """사용 이벤트 사이드카 로그(`~/.pouch/usage.jsonl`).

    카탈로그(레지스트리)와 분리된 append-only 라이프사이클 레이어.
    """
    return global_root() / "usage.jsonl"


def project_usage_log_path(start: Path | None = None) -> Path | None:
    """현재 프로젝트의 로컬 사용 로그(`<repo>/.pouch/usage.jsonl`). 프로젝트 밖이면 None.

    맥락 개인화(레인 2a)의 P3 프라이버시 자리 — 프로젝트별 사용 기록은 그 repo의
    `.pouch/`에만 남긴다(로컬 전용). 전역 백업(`~/.pouch`)엔 안 들어가므로 프로젝트
    경로·맥락이 클라우드로 새지 않는다("프로젝트 `.pouch`는 클라우드 안 나간다"와 정렬).
    """
    root = find_project_root(start)
    return (root / ".pouch" / "usage.jsonl") if root else None


def usage_summary_path() -> Path:
    """접힌 사용 요약(`~/.pouch/usage-summary.json`).

    오래된(경계 밖) 이벤트를 entry_id별 누적으로 접어 보존한다. 개별 시각은
    흐려지되 누적 횟수(습관 신호)는 남는다. `compacted_through` 마커로 집계가
    jsonl의 접힌 구간을 무시해 이중 계산을 막는다(멱등).
    """
    return global_root() / "usage-summary.json"


def state_path() -> Path:
    """활성 표면 상태 사이드카(`~/.pouch/state.json`).

    entry_id → installed_at·status. 카탈로그와 분리된 라이프사이클 기록.
    """
    return global_root() / "state.json"


def sweep_marker_path() -> Path:
    """도구통 훑기 표식(`~/.pouch/sweep.json`).

    "이 주머니가 한 번이라도 훑은 적 있나"만 담는다. init은 처음 한 번만 도니까,
    이미 pouch를 쓰던 사람에게 훑기를 한 번 알려주려면 이 근거가 필요하다.
    state.json(도구별 설치 기록)과 스키마가 달라 섞지 않고 따로 둔다.
    """
    return global_root() / "sweep.json"


def proposals_ledger_path() -> Path:
    """제안 장부 사이드카(`~/.pouch/proposals.json`).

    proposal_id → last_shown_at·shown_count. 먼저 내미는 제안의 잔소리 방어
    (간격·묵히기)가 요구하는 작은 상태. usage.jsonl·state.json과 같은 정신 —
    카탈로그와 분리된, 버려도 되는 라이프사이클 레이어(지우면 다시 침묵부터 시작).
    """
    return global_root() / "proposals.json"


def anchor_path() -> Path:
    """글로벌 정렬 앵커 사이드카(`~/.pouch/anchor.json`).

    "이번 작업 목표" 한 줄을 고정하는 자리 중 *프로젝트 밖* 몫. proposals.json과 같은
    정신 — 카탈로그와 분리된, 버려도 되는 라이프사이클 레이어. compaction으로
    목표가 흐려져도 이 사이드카가 ◆목표 슬롯의 재해석 없는 고정점이 된다.
    """
    return global_root() / "anchor.json"


def project_anchor_path(start: Path | None = None) -> Path | None:
    """현재 프로젝트의 앵커(`<repo>/.pouch/anchor.json`). 프로젝트 밖이면 None.

    memory·catalog가 global/project 2계층인 것과 같은 확장이다.
    """
    root = find_project_root(start)
    return (root / ".pouch" / "anchor.json") if root else None


def resolve_anchor_path(start: Path | None = None) -> Path:
    """지금 여기서 쓸 앵커 자리 — 프로젝트 안이면 프로젝트 것, 밖이면 글로벌.

    **글로벌로 폴백하지 않는다**(프로젝트 안이면 프로젝트 앵커가 없어도 글로벌을
    읽지 않는다). 앵커가 하나뿐이라 A 프로젝트의 목표가 B 프로젝트 세션 시작에
    그대로 주입되던 사고(2026-07-21)를 자리 자체로 막는 게 목적이다 — 폴백을
    허용하는 순간 오염 경로가 되살아난다.
    """
    return project_anchor_path(start) or anchor_path()


def backup_dir() -> Path:
    """로컬 백업 목적지(`~/pouch-backups/`). `POUCH_BACKUP_DIR`로 오버라이드 가능.

    글로벌 루트(`~/.pouch`)의 *형제*라 백업 아카이브가 백업 대상 안에 들어가는
    재귀를 구조적으로 피한다. 복원 직전 자동 스냅샷도 여기에 함께 쌓인다.
    """
    override = os.environ.get("POUCH_BACKUP_DIR")
    return Path(override).expanduser() if override else Path.home() / "pouch-backups"


def find_project_root(start: Path | None = None) -> Path | None:
    """`.pouch/` 또는 `.git`이 있는 가장 가까운 상위 디렉토리를 찾는다."""
    start = (start or Path.cwd()).resolve()
    for directory in (start, *start.parents):
        if (directory / ".pouch").is_dir() or (directory / ".git").exists():
            return directory
    return None


def project_memory_dir(start: Path | None = None) -> Path | None:
    """현재 프로젝트의 메모리 디렉토리. 프로젝트 루트를 못 찾으면 None."""
    root = find_project_root(start)
    return (root / ".pouch" / "memory") if root else None


def claude_settings_path() -> Path:
    """Claude Code 사용자 설정 파일 경로(`~/.claude/settings.json`).

    `CLAUDE_CONFIG_DIR` 환경변수로 오버라이드 가능(테스트/대체 설치 위치).
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "settings.json"


def claude_project_memory_dir(project_root: Path) -> Path:
    """주어진 프로젝트 루트의 Claude 네이티브 메모리 디렉토리.

    네이티브는 프로젝트 경로를 슬러그(`/`→`-`)로 접어 `~/.claude/projects/<슬러그>/memory/`에
    담는다. adopt(대체 A안 §2)가 이 자리를 훑어 pouch로 이관한다. `CLAUDE_CONFIG_DIR`로
    베이스를 오버라이드할 수 있다(테스트/대체 설치 위치).
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    slug = str(project_root.resolve()).replace("/", "-")
    return base / "projects" / slug / "memory"


def claude_skills_dir() -> Path:
    """Claude Code 스킬 설치 위치(`~/.claude/skills/`).

    `CLAUDE_CONFIG_DIR` 환경변수로 오버라이드 가능(테스트/대체 설치 위치).
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "skills"


def claude_plugins_cache_dir() -> Path:
    """Claude Code 플러그인 캐시(`~/.claude/plugins/cache/`).

    실측(2026-07-21): 안쪽이 `<마켓>/<플러그인>/<버전>/` 3단이라 이 경로를 그대로
    classify하면 실패한다 — find_plugin_roots로 파고들어야 한다(훑기가 그렇게 쓴다).
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "plugins" / "cache"


def claude_agents_dir() -> Path:
    """Claude Code 에이전트 서랍(`~/.claude/agents/`) — 평면 `<이름>.md`."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "agents"


def claude_commands_dir() -> Path:
    """Claude Code 명령 서랍(`~/.claude/commands/`) — 평면 `<이름>.md`."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "commands"


def claude_rules_dir() -> Path:
    """Claude Code 규칙 폴더(`~/.claude/rules/`).

    다른 서랍과 달리 `<분류>/<이름>.md`로 한 겹 더 들어가기도 한다(실측: 최상위 11개
    + 하위 88개). 그래서 같은 파일명이 여러 곳에 겹치고, id를 `부모__이름`으로 접는다.
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / "rules"


def claude_mcp_config_path() -> Path:
    """Claude Code 전역 MCP 설정(`~/.claude/.mcp.json`)."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".claude"
    return base / ".mcp.json"


def codex_home() -> Path:
    """Codex 전역 루트(`~/.codex/`). `CODEX_HOME`으로 오버라이드 가능."""
    override = os.environ.get("CODEX_HOME")
    return Path(override).expanduser() if override else Path.home() / ".codex"


def codex_hooks_path() -> Path:
    """Codex 훅 설정 파일 경로(`~/.codex/hooks.json`).

    `CODEX_HOME` 환경변수로 오버라이드 가능(테스트/대체 설치 위치). Codex는
    Claude Code와 훅 JSON 스키마가 같아 claude 어댑터의 순수 함수를 재사용한다 —
    다른 건 이 경로와, 설치 후 안내(experimental 플래그·훅 신뢰 등록)뿐이다.
    """
    return codex_home() / "hooks.json"


def codex_skills_dir() -> Path:
    """Codex 스킬 폴더(`~/.codex/skills/`) — 실측 2026-07-21."""
    return codex_home() / "skills"


def kiro_home() -> Path:
    """Kiro 전역 루트(`~/.kiro/`) — 이 머신에 Kiro가 깔렸는지의 신호.

    `KIRO_HOME` 환경변수로 오버라이드 가능(테스트/대체 설치 위치). Kiro 앱은 홈에
    이 디렉토리를 만든다(steering·settings·sessions 등). 프로젝트별 `.kiro/`와
    다른, 전역 설치 표식이다.
    """
    override = os.environ.get("KIRO_HOME")
    return Path(override).expanduser() if override else Path.home() / ".kiro"


def kiro_skills_dir() -> Path:
    """Kiro 스킬 폴더(`~/.kiro/skills/`) — 실측 2026-07-21.

    Kiro는 기억을 steering 파일로만 받지만(사용 로깅 불가) 도구통은 따로 있다.
    "기억을 어떻게 넣나"와 "도구를 어디 두나"는 서로 다른 축이다.
    """
    return kiro_home() / "skills"


def kiro_steering_path() -> Path:
    """Kiro 전역 steering 파일(`~/.kiro/steering/pouch-memory.md`).

    모든 워크스페이스에서 항상 읽히는 자리(inclusion: always). 그래서 여기엔
    전역 기억만 담는다 — 프로젝트 기억을 넣으면 다른 프로젝트로 샌다. 훅과 달리
    "한 번 찍는 사진"이라, 기억이 바뀌면 filesync가 다시 쓴다.
    """
    return kiro_home() / "steering" / "pouch-memory.md"


def project_mcp_config_path(start: Path | None = None) -> Path:
    """현재 프로젝트의 `.mcp.json` 경로. 프로젝트 루트를 못 찾으면 cwd 기준."""
    root = find_project_root(start) or (start or Path.cwd())
    return root / ".mcp.json"
