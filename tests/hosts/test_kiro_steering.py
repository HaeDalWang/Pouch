"""Kiro steering 파일 어댑터 검증 — 탐지·frontmatter·링크/해제·백업.

훅이 아니라 홈 파일이라 계약이 다르다: is_supported(전역 설치 신호)·link(스냅샷
기록)·is_linked(파일 존재)·unlink. inclusion:always frontmatter가 맨 앞에 오는지가
핵심(Kiro가 그래야 모든 세션에 싣는다).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pouch.hosts.kiro import KiroSteeringAdapter

adapter = KiroSteeringAdapter()


@pytest.fixture
def kiro_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "kiro"
    monkeypatch.setenv("KIRO_HOME", str(home))
    return home


def test_not_supported_when_home_absent(kiro_home: Path) -> None:
    # KIRO_HOME은 가리키지만 디렉토리는 아직 없음 → 미설치로 본다.
    assert not adapter.is_supported()


def test_supported_when_home_exists(kiro_home: Path) -> None:
    kiro_home.mkdir()
    assert adapter.is_supported()


def test_link_writes_frontmatter_first(kiro_home: Path) -> None:
    kiro_home.mkdir()
    adapter.link("# 기억\n- 내용")
    text = adapter.content_path().read_text(encoding="utf-8")
    # frontmatter가 파일 맨 앞(빈 줄·내용 없이)에 와야 Kiro가 always 로드한다.
    assert text.startswith("---\ninclusion: always\n---\n")
    assert "# 기억" in text


def test_is_linked_reflects_file(kiro_home: Path) -> None:
    kiro_home.mkdir()
    assert not adapter.is_linked()
    adapter.link("본문")
    assert adapter.is_linked()


def test_unlink_removes(kiro_home: Path) -> None:
    kiro_home.mkdir()
    adapter.link("본문")
    assert adapter.unlink()
    assert not adapter.is_linked()
    assert not adapter.unlink()  # 두 번째는 지울 게 없음


def test_relink_backs_up(kiro_home: Path) -> None:
    kiro_home.mkdir()
    adapter.link("첫 본문")
    backup = adapter.link("둘째 본문")
    assert backup is not None and backup.exists()
    assert "첫 본문" in backup.read_text(encoding="utf-8")
    assert "둘째 본문" in adapter.content_path().read_text(encoding="utf-8")
