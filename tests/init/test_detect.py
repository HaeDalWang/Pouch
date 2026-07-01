"""환경 감지 — 순수 파싱은 단위로, 실제 감지는 통합으로 검증."""

from __future__ import annotations

import pouch.init.detect as detect
from pouch.init.detect import detect_environment, detect_runtimes, parse_version


def test_parse_version_python() -> None:
    assert parse_version("Python 3.14.4") == "3.14.4"


def test_parse_version_node() -> None:
    assert parse_version("v20.1.0") == "20.1.0"


def test_parse_version_go() -> None:
    assert parse_version("go version go1.22 darwin/arm64") == "1.22"


def test_parse_version_returns_none_without_digits() -> None:
    assert parse_version("no version here") is None


def test_detect_environment_has_os() -> None:
    # Act
    env = detect_environment()

    # Assert — platform.system()은 항상 비어있지 않음
    assert env.os


def test_detect_environment_finds_python() -> None:
    # Act — 테스트가 python3로 도는 이상 python은 감지돼야 함
    env = detect_environment()

    # Assert
    assert "python" in env.runtime_names()


def test_detect_runtimes_excludes_version_unparseable(monkeypatch) -> None:
    # java 스텁 함정: PATH엔 있지만(which 통과) -version이 버전을 안 내놓는 경우.
    # 존재는 필요조건이지 충분조건이 아니다 — 버전이 실제 사용 가능의 증거다.
    monkeypatch.setattr(detect.shutil, "which", lambda _cmd: "/usr/bin/" + _cmd)
    monkeypatch.setattr(detect, "_run_version", lambda cmd, *a: None if cmd == "java" else "1.0")

    names = [rt.name for rt in detect_runtimes()]

    assert "java" not in names  # 빈 값으로 새어들지 않는다
    assert "python" in names  # 버전 잡힌 건 그대로


def test_detect_runtimes_all_have_versions(monkeypatch) -> None:
    # 감지 결과의 모든 런타임은 version을 가진다(None 없음) — 오염원 차단.
    monkeypatch.setattr(detect.shutil, "which", lambda cmd: "/usr/bin/" + cmd)
    monkeypatch.setattr(detect, "_run_version", lambda cmd, *a: None if cmd == "java" else "1.0")

    assert all(rt.version is not None for rt in detect_runtimes())
