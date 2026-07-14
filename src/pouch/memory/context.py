"""세션 컨텍스트 렌더링 — SessionStart hook이 에이전트에게 주입할 인덱스.

일반 메모리는 인덱스(이름·성격·한 줄 요약)만 주입한다.
에이전트는 필요할 때 `pouch memory recall <키워드>`로 본문을 끌어온다.

단 `boundary`(자율성/신뢰 경계)는 예외다. 본문까지 최상단에 강조 주입하며,
"금지는 넓게, 허용은 좁게"라는 해석 지침을 함께 박아 deny 오독을 완화한다.
허용 누수(A 프로젝트 → B)는 scope 저장 구조가 막는다(프로젝트 경계는 그 repo에서만 읽힘).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from pouch.checkpoint.anchor import Anchor
from pouch.checkpoint.render import render_checkpoint_protocol
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryType


def render_session_context(
    entries: Iterable[MemoryEntry],
    *,
    anchor: Anchor | None = None,
    note_zone: Callable[[], str] | None = None,
) -> str:
    """SessionStart 통로 전체 — 고정 구역(반드시 읽음) + 쪽지 구역(무시 가능).

    가르는 축은 churn이 아니라 "반드시 읽어야 함 vs 무시돼도 됨". boundary·정렬
    체크포인트 규약·기억 인덱스는 고정 구역(위), 먼저 내미는 제안 쪽지는 쪽지
    구역(아래, 조건부).

    체크포인트 규약은 앵커 유무·기억 유무와 무관하게 항상 고정 구역에 실린다
    (기능의 핵심 — 기억이 0개여도 "갈림길에서 방향 맞추기" 지침은 주입돼야 한다).
    경계와 기억 인덱스 사이에 끼운다(안전 경계가 최상단을 유지, 규약은 그 아래).

    격리 불변식 — 한 구현으로 ①+③ 동시 만족:
      먼저 고정 구역을 완전히 렌더·확정한다(entries 소비·규약 렌더가 여기서
      일어나므로, 고정 구역이 터지면 쪽지 로직에 닿기도 전에 시끄럽게 실패한다 —
      가드레일 없는 제안-only 컨텍스트가 새어나가는 것을 막는 비대칭 ③b).
      그다음 쪽지를 격리된 try 안에서 시도한다(터져도 고정 구역은 이미 나갔으니
      생존 ③a, 위로도 못 옴 ①). note_zone이 None이거나 빈 내용이면 쪽지 구역은
      아예 안 그려진다(문턱 미달 = 글자 0, 구분선조차 없음 ②).
    """
    # 고정 구역 먼저 — 실패는 여기서 전파(③b). 규약은 entries 유무와 독립 주입.
    fixed = render_context(entries, extra_fixed=render_checkpoint_protocol(anchor))
    if note_zone is None:
        return fixed

    try:
        note = note_zone()
    except Exception:  # noqa: BLE001 — 쪽지 실패는 조용히 흡수(③a), 고정 구역은 이미 확정
        return fixed

    if not note.strip():  # 문턱 미달 → 쪽지 구역 자체를 안 그린다(②)
        return fixed

    # 쪽지는 항상 고정 구역 아래(①). 구분선은 내용이 있을 때만 등장.
    return fixed.rstrip() + "\n\n---\n\n" + note.strip() + "\n"


def render_context(
    entries: Iterable[MemoryEntry],
    *,
    extra_fixed: list[str] | None = None,
) -> str:
    """주입용 마크다운을 만든다. 기억도 extra_fixed도 없으면 빈 문자열(주입 생략).

    extra_fixed는 경계와 기억 인덱스 사이에 끼우는 고정 구역 줄들이다(정렬 체크포인트
    규약 등). 기억이 0개여도 extra_fixed가 있으면 헤더와 함께 주입된다 — 규약이
    기억 유무와 독립적으로 실려야 하기 때문이다.
    """
    ordered = list(entries)
    if not ordered and not extra_fixed:
        return ""

    boundaries = sorted(
        (entry for entry in ordered if entry.type is MemoryType.BOUNDARY),
        key=lambda entry: entry.name,
    )
    others = [entry for entry in ordered if entry.type is not MemoryType.BOUNDARY]

    lines = [
        "# 🦦 pouch memory — 사용자에 대해 기억하는 것",
        "",
        "아래는 pouch가 기억해 둔 사용자·프로젝트 맥락이다. 이를 참고해 응답하라.",
        "더 자세한 내용이 필요하면 `pouch memory recall <키워드>`로 본문을 가져올 수 있다.",
        "",
    ]
    if boundaries:
        lines.extend(_render_boundaries(boundaries))
    if extra_fixed:
        lines.extend(extra_fixed)
    lines.extend(_render_scoped(others))
    return "\n".join(lines).rstrip() + "\n"


def _render_boundaries(boundaries: list[MemoryEntry]) -> list[str]:
    """자율성 경계를 본문까지 포함해 최상단에 강조 렌더링한다."""
    lines = [
        "## ⚠️ 자율성 경계 — 반드시 따를 것",
        "",
        "각 항목 앞 대괄호 라벨([DENY]/[ASK]/[ALLOW])이 방향의 권위다 — "
        "본문 산문이 애매하면 라벨을 따르라. "
        "금지(deny)는 항상 우선하며 넓게 해석하라. "
        "허용(allow)은 아래에 적힌 범위 안에서만 좁게 적용하라. "
        "확인(ask)은 실행 전 사용자에게 물어라. "
        "프로젝트 범위 허용을 이 프로젝트 밖으로 확장하지 마라.",
        "",
    ]
    for entry in boundaries:
        label = f"[{entry.direction.value.upper()}] " if entry.direction else ""
        lines.append(f"- {label}**{entry.name}** [{entry.scope.value}] — {entry.description}")
        body = entry.body.strip()
        if body:
            lines.extend(f"  {body_line}" for body_line in body.splitlines())
    lines.append("")
    return lines


def _render_scoped(entries: list[MemoryEntry]) -> list[str]:
    """일반 메모리를 스코프별로 인덱스만 렌더링한다."""
    lines: list[str] = []
    for scope in (MemoryScope.GLOBAL, MemoryScope.PROJECT):
        scoped = sorted(
            (entry for entry in entries if entry.scope is scope),
            key=lambda entry: entry.name,
        )
        if not scoped:
            continue
        lines.append(f"## {scope.value}")
        lines.extend(
            f"- **{entry.name}** ({entry.type.value}) — {entry.description}" for entry in scoped
        )
        lines.append("")
    return lines
