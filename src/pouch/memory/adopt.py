"""네이티브 메모리 이관 — Claude Code 기본 메모리를 pouch로 들이는 순수 코어.

[MEMORY-REPLACE-DESIGN.md]의 A안(대체)의 §2. 네이티브 메모리 파일(frontmatter의
`metadata.type`으로 성격을 밝힘)을 pouch MemoryEntry로 바꾸되, 두 가지를 결정한다:

  스코프 — 타입이 자리를 정한다. user·feedback는 "너·일하는 법"이라 global,
           project·reference는 "그 작업에 매인 것"이라 project.
  계층   — 네이티브는 생명주기가 없어 세션로그까지 전부 상시 주입했다. 이관은
           "안정 핵심만 주입"을 복원한다: user·feedback·reference는 INDEXED(주입),
           project(대개 날짜 박힌 세션 맥락)는 PENDING(주입 안 함·리뷰 대기·recall 가능).

파일 IO(디렉토리 훑기·mtime·저장)와 시계는 호출부(명령 경계)의 몫이다 — 이 모듈은
파싱된 텍스트와 주입받은 created 날짜만으로 순수하게 결정한다(now 주입과 같은 경계 원칙).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import frontmatter

from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState, MemoryType

# 네이티브 metadata.type → pouch 타입. boundary는 네이티브에 없어 매핑에 없다.
_TYPE_MAP: dict[str, MemoryType] = {
    "user": MemoryType.USER,
    "feedback": MemoryType.FEEDBACK,
    "project": MemoryType.PROJECT,
    "reference": MemoryType.REFERENCE,
}

# 타입 → (scope, state, 사람이 읽을 이유). 스코프·계층 결정의 단일 출처.
_ROUTING: dict[MemoryType, tuple[MemoryScope, MemoryState, str]] = {
    MemoryType.USER: (MemoryScope.GLOBAL, MemoryState.INDEXED, "안정 핵심 — 전역 주입"),
    MemoryType.FEEDBACK: (MemoryScope.GLOBAL, MemoryState.INDEXED, "안정 핵심 — 전역 주입"),
    MemoryType.REFERENCE: (
        MemoryScope.PROJECT,
        MemoryState.INDEXED,
        "프로젝트 참조 — 주입(생존성은 이후 위생이 확인)",
    ),
    MemoryType.PROJECT: (
        MemoryScope.PROJECT,
        MemoryState.PENDING,
        "세션 맥락일 수 있음 — 리뷰 대기(주입 안 함·recall 가능)",
    ),
}

# 파일명·frontmatter name을 pouch 파일명(=name)으로 쓸 안전한 글자만 남긴다.
_UNSAFE_RE = re.compile(r"[^a-zA-Z0-9_-]+")

# 세션로그 신호 — 이름에 박힌 YYMMDD(6자리) 날짜 토큰. 월·일이 유효할 때만 날짜로
# 본다(issue 번호 "121314" 같은 6자리 오탐 방지). project 이관 계층을 PENDING↔ARCHIVED로
# 가른다: 날짜 박힌 세션로그는 명백히 지난 맥락이라 리뷰 잔소리에서 빼고 recall만 남긴다.
_DATE_TOKEN_RE = re.compile(r"(?<![0-9])(\d{2})(\d{2})(\d{2})(?![0-9])")


def _looks_dated(name: str) -> bool:
    """이름에 유효한 YYMMDD 날짜 토큰이 있는지(명백한 세션로그 신호)."""
    return any(
        1 <= int(mm) <= 12 and 1 <= int(dd) <= 31
        for _yy, mm, dd in _DATE_TOKEN_RE.findall(name)
    )


@dataclass(frozen=True)
class AdoptionItem:
    """이관 계획 한 건 — 무엇이 어디로·어떤 계층으로 갈지(순수 결정)."""

    entry: MemoryEntry
    source_path: str  # 원본 네이티브 파일(보고용 — 이관은 복사라 원본은 안 지운다)
    reason: str  # 왜 이 계층인가(사람이 읽을 한 줄)


@dataclass(frozen=True)
class SkippedNative:
    """이관에서 건너뛴 파일 — 조용히 삼키지 않고 이유와 함께 보고한다."""

    source_path: str
    reason: str


def _native_type(meta: dict) -> str | None:
    """네이티브 frontmatter에서 memory 타입을 뽑는다. `metadata.type` 우선, 없으면 평면 `type`."""
    nested = meta.get("metadata")
    if isinstance(nested, dict) and nested.get("type"):
        return str(nested["type"])
    flat = meta.get("type")
    return str(flat) if flat else None


def _derive_name(meta: dict, stem: str, native_type: str) -> str:
    """pouch name(=파일명)을 정한다. frontmatter name 우선, 없으면 stem.

    어느 쪽에서 왔든 중복되는 타입 접두(`<type>_`)는 벗긴다 — 타입은 이미 별도
    필드라, 네이티브가 파일명·name에 박아둔 `feedback_`·`project_` 접두를 그대로
    끌고 오면 이름이 지저분해진다. 접두 뒤에 `_`가 올 때만 벗겨 오탐을 막는다
    (예: project_type인 "projection_foo"는 안 건드림).
    """
    raw = str(meta.get("name") or "").strip() or stem
    prefix = f"{native_type}_"
    if raw.startswith(prefix):
        raw = raw[len(prefix):]
    safe = _UNSAFE_RE.sub("-", raw).strip("-")
    return safe or stem


def plan_native_file(
    text: str, *, source_path: str, stem: str, created: date
) -> AdoptionItem | SkippedNative:
    """네이티브 메모리 한 건을 이관 결정으로 바꾼다(순수).

    타입을 못 읽거나 매핑에 없으면(예: 알 수 없는 타입) SkippedNative를 돌려준다 —
    호출부가 조용히 삼키지 않고 이유와 함께 보고한다. frontmatter가 깨져 파싱이
    터지는 경우(실데이터엔 따옴표 없는 콜론 등이 있다)도 전체 이관을 멈추지 않고
    이 파일만 건너뛴다 — 이관은 복사라 원본 네이티브 파일은 그대로 남는다.
    """
    try:
        post = frontmatter.loads(text)
    except Exception as exc:  # noqa: BLE001 — 깨진 frontmatter는 크래시가 아니라 건너뜀
        return SkippedNative(source_path, f"frontmatter 파싱 실패: {type(exc).__name__}")
    native_type = _native_type(post.metadata)
    if native_type is None:
        return SkippedNative(source_path, "타입 없음(metadata.type/type 모두 비어 있음)")
    mem_type = _TYPE_MAP.get(native_type)
    if mem_type is None:
        return SkippedNative(source_path, f"알 수 없는 타입 '{native_type}'")

    scope, state, reason = _ROUTING[mem_type]
    name = _derive_name(post.metadata, stem, native_type)
    # 세션로그 휴리스틱: project 기억 이름에 YYMMDD가 박혀 있으면 명백한 지난 세션
    # 맥락이라 ARCHIVED(주입 X·recall O·리뷰 잔소리 없음). 날짜 없는 project는 PENDING 유지.
    if mem_type is MemoryType.PROJECT and _looks_dated(name):
        state = MemoryState.ARCHIVED
        reason = "날짜 박힌 세션로그 — 보관(주입 X·recall O·리뷰 잔소리 없음)"
    entry = MemoryEntry(
        name=name,
        description=str(post.metadata.get("description") or ""),  # 빈 description(YAML None)이 "None"이 되지 않게
        body=post.content,
        type=mem_type,
        scope=scope,
        state=state,
        created=created,
    )
    return AdoptionItem(entry=entry, source_path=source_path, reason=reason)


def partition_existing(
    items: list[AdoptionItem],
    *,
    existing: set[tuple[str, MemoryScope]],
) -> tuple[list[AdoptionItem], list[SkippedNative]]:
    """이미 pouch에 있는 이름은 이관에서 뺀다(덮어쓰기 방지). 배치 내 동명도 첫 것만 담는다.

    "떨어진다 ≠ 삭제된다"의 이관판 — 사용자가 이미 가진(또는 promote한) 기억을 말없이
    덮지 않는다. 세 갈래 소실을 여기서 막는다: (a) 기존 pouch 기억과 충돌, (b) 재실행 시
    promote된 상태 리셋, (c) 배치 내 두 native 파일이 같은 이름으로 파생. 건너뛴 건 이유와
    함께 보고한다(조용히 안 삼킴). existing은 (name, scope) 집합으로 호출부가 주입한다.
    """
    kept: list[AdoptionItem] = []
    skipped: list[SkippedNative] = []
    seen: set[tuple[str, MemoryScope]] = set()
    for item in items:
        key = (item.entry.name, item.entry.scope)
        if key in existing:
            skipped.append(SkippedNative(item.source_path, "이미 pouch에 있음(덮어쓰기 방지)"))
        elif key in seen:
            skipped.append(SkippedNative(item.source_path, "이관 배치 내 이름 중복(첫 항목만 담음)"))
        else:
            seen.add(key)
            kept.append(item)
    return kept, skipped
