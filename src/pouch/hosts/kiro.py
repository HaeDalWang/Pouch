"""Kiro 어댑터 — 홈 steering 파일에 기억 스냅샷을 쓴다(파일 호스트).

Kiro 훅은 워크스페이스 스코프뿐이라 새 프로젝트마다 다시 걸어야 했다. 대신 Kiro는
`~/.kiro/steering/`에 두면 모든 워크스페이스에서 항상 읽히는 파일을 지원한다
(`inclusion: always`). 그래서 pouch는 훅 대신 이 파일에 기억을 스냅샷으로 써둔다 —
홈에 한 번, 이후 기억이 바뀌면 filesync가 다시 쓴다.

맞바꿈: 파일은 컨텍스트 주입만 하고 사용 로깅(도구 호출 기록)은 못 한다. 그건 주로
Claude Code에서 쌓이므로 손실은 작다(post_install_notes로 정직하게 안내).
"""

from __future__ import annotations

from pathlib import Path

from pouch import paths
from pouch.hosts.base import LAYOUT_SKILLS_ROOT, Toolbox
from pouch.hosts.filewrite import write_snapshot

# steering 파일 맨 앞에 오는 frontmatter — 모든 세션에 항상 실리게 한다.
# "must be the first content in the file, no blank lines before it"라는 Kiro 규칙을 따른다.
_FRONTMATTER = "---\ninclusion: always\n---\n\n"


class KiroSteeringAdapter:
    """Kiro(`~/.kiro/steering/pouch-memory.md`) 파일 배선."""

    name = "kiro"
    display_name = "Kiro"

    def is_supported(self) -> bool:
        return paths.kiro_home().exists()

    def toolbox_paths(self) -> tuple[Toolbox, ...]:
        """Kiro도 도구통이 있다(`~/.kiro/skills/`, 실측 2026-07-21).

        기억은 파일로만 받지만(사용 로깅 불가) 도구는 따로 둔다 — 두 축이 다르다.
        """
        return (Toolbox(path=paths.kiro_skills_dir(), layout=LAYOUT_SKILLS_ROOT),)

    def content_path(self) -> Path:
        return paths.kiro_steering_path()

    def is_linked(self) -> bool:
        return self.content_path().exists()

    def link(self, body: str) -> Path | None:
        return write_snapshot(self.content_path(), _FRONTMATTER + body)

    def unlink(self) -> bool:
        path = self.content_path()
        if not path.exists():
            return False
        path.unlink()
        return True

    def post_install_notes(self) -> list[str]:
        return [
            "Kiro는 홈 steering 파일로 연결됩니다 — 모든 Kiro 프로젝트에서 읽힙니다.",
            "기억을 담거나 지우면 이 파일은 자동으로 다시 쓰입니다(항상 최신).",
            "단, Kiro는 이 방식에선 '사용 로깅'이 안 됩니다(도구 사용 기록은 Claude Code에서 쌓입니다).",
        ]
