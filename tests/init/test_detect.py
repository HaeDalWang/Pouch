"""환경 감지 — 순수 파싱은 단위로, 실제 감지는 통합으로 검증."""

from __future__ import annotations

from pouch.init.detect import detect_environment, parse_version


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
