"""환경 감지 — 마법사가 묻기 전에 자동으로 알아낼 수 있는 것들.

버전 파싱은 순수 함수로 분리해 단위 테스트하고, 외부 명령 실행은
얇은 IO 래퍼로 감싼다. 감지 실패는 None으로 흡수한다(마법사를 막지 않음).
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass

_VERSION_RE = re.compile(r"\d+\.\d+(?:\.\d+)?")
_PROBE_TIMEOUT = 5

# 감지할 런타임: name -> (which로 찾을 명령, 버전 인자...)
_RUNTIME_PROBES: dict[str, tuple[str, ...]] = {
    "python": ("python3", "--version"),
    "node": ("node", "--version"),
    "go": ("go", "version"),
    "rust": ("rustc", "--version"),
    "java": ("java", "-version"),
    "ruby": ("ruby", "--version"),
}


@dataclass(frozen=True)
class Runtime:
    """감지된 언어 런타임."""

    name: str
    version: str | None


@dataclass(frozen=True)
class Environment:
    """자동 감지된 사용자 환경 스냅샷."""

    os: str
    shell: str | None
    git_email: str | None
    runtimes: tuple[Runtime, ...]
    has_claude: bool

    def runtime_names(self) -> list[str]:
        return [runtime.name for runtime in self.runtimes]


def parse_version(output: str) -> str | None:
    """명령 출력에서 첫 `x.y[.z]` 버전 문자열을 뽑는다."""
    match = _VERSION_RE.search(output)
    return match.group(0) if match else None


def _run_version(command: str, *args: str) -> str | None:
    """버전 명령을 실행해 파싱한다. 실패는 None(일부 도구는 stderr로 출력)."""
    try:
        result = subprocess.run(  # noqa: S603
            [command, *args],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(result.stdout + result.stderr)


def detect_runtimes() -> tuple[Runtime, ...]:
    """PATH에 존재하는 런타임만 감지한다."""
    found: list[Runtime] = []
    for name, probe in _RUNTIME_PROBES.items():
        command, *args = probe
        if shutil.which(command) is None:
            continue
        found.append(Runtime(name=name, version=_run_version(command, *args)))
    return tuple(found)


def _git_email() -> str | None:
    if shutil.which("git") is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "config", "--get", "user.email"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def detect_environment() -> Environment:
    """현재 환경을 한 번에 감지한다."""
    home = os.path.expanduser("~")
    return Environment(
        os=platform.system(),
        shell=os.environ.get("SHELL"),
        git_email=_git_email(),
        runtimes=detect_runtimes(),
        has_claude=os.path.isdir(os.path.join(home, ".claude")),
    )
