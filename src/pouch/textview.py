"""화면용 텍스트 손질 — 여러 CLI 화면이 같이 쓰는 작은 도구.

evolution('이거 써봐')과 repos(색인 검색)가 같은 자르기를 쓰게 한 곳에 둔다 —
복붙이 갈라지면 화면마다 설명 길이가 달라진다.
"""

from __future__ import annotations

DESC_CLIP = 90  # 설명은 첫 숨까지만 — SKILL.md 설명 전문은 화면을 뒤덮는다


def clip(text: str, limit: int = DESC_CLIP) -> str:
    """설명을 한 줄 요약 길이로 자른다(개행·연속 공백은 하나로 접는다)."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"
