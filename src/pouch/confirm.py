"""물어보기 — typer.confirm에 한글 입력기 안전판을 씌운다.

전각 공백(한글 자판의 넓은 스페이스) 같은 비ASCII 문자가 답에 섞이면
typer/click이 UnicodeDecodeError로 즉사한다 — 2026-07-18 실사용에서 잡힌
사고. 한국어 사용자에겐 입력기가 남기는 자연스러운 흔적이라, 죽는 대신
되묻는다. 계속 못 읽으면(입력 스트림 자체가 깨짐) 안전한 쪽으로 접는다:
아니오 — pouch는 동의 없인 아무것도 안 움직인다.

모든 동의 물음은 typer.confirm 대신 이 confirm을 쓴다.
"""

from __future__ import annotations

import typer
from rich.console import Console

_console = Console()
_MAX_ATTEMPTS = 3  # 같은 오류가 이만큼 반복되면 되묻기를 멈춘다


def confirm(message: str, *, default: bool = False) -> bool:
    """예/아니오를 묻는다 — 못 읽는 입력엔 되묻고, 끝내 못 읽으면 아니오."""
    for _ in range(_MAX_ATTEMPTS):
        try:
            return typer.confirm(message, default=default)
        except UnicodeDecodeError:
            _console.print(
                "  [yellow]![/yellow] 입력을 못 읽었어요(전각 문자가 섞였나요?) — "
                "영문 y 또는 n으로 다시 답해주세요."
            )
    return False
