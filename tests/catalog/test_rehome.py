"""rehome 계약 검증 — 죽은 upstream 경로를 형제 버전 디렉토리로 재해석한다.

플러그인 캐시는 <marketplace>/<plugin>/<version>/ 구조라, 플러그인이 업데이트
되면 버전 디렉토리가 통째로 사라지고 vendored upstream 194개가 동시에 죽는다.
재해석 계약:
  ① 사라진 컴포넌트의 형제 중, 나머지 경로(rest)가 실존하는 최신 버전을 고른다
  ② pre-release(rc)는 같은 release의 정식판보다 낮다 (2.0.0-rc.2 < 2.0.0)
  ③ rest가 없는 형제는 버전이 높아도 후보가 아니다
  ④ 후보가 없으면 None (완전 증발 — 판단은 호출부가)
  ⑤ 숨김 디렉토리는 후보가 아니다 (.backup 등 사본 오염 방지)
"""

from __future__ import annotations

from pathlib import Path

from pouch.catalog.rehome import rehome_upstream

_REST = ("skills", "aws-iam", "SKILL.md")


def _make_version(base: Path, version: str, *, with_skill: bool = True) -> Path:
    """<base>/cache/mkt/plug/<version>/skills/aws-iam/SKILL.md 구조를 만든다."""
    version_dir = base / "cache" / "mkt" / "plug" / version
    skill_path = version_dir.joinpath(*_REST)
    if with_skill:
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("---\nname: aws-iam\n---\n", encoding="utf-8")
    else:
        version_dir.mkdir(parents=True)
    return skill_path


def _dead(base: Path, version: str) -> str:
    """존재하지 않는 버전을 가리키는 죽은 upstream 경로."""
    return str(base / "cache" / "mkt" / "plug" / version / Path(*_REST))


def test_contract1_picks_sibling_version_with_same_rest(tmp_path: Path) -> None:
    new_skill = _make_version(tmp_path, "2.0.0")

    result = rehome_upstream(_dead(tmp_path, "2.0.0-rc.1"))

    assert result == new_skill


def test_contract2_prerelease_ranks_below_release(tmp_path: Path) -> None:
    _make_version(tmp_path, "1.9.9")
    _make_version(tmp_path, "2.0.0-rc.2")
    release = _make_version(tmp_path, "2.0.0")

    result = rehome_upstream(_dead(tmp_path, "2.0.0-rc.1"))

    assert result == release


def test_contract3_sibling_without_rest_is_not_candidate(tmp_path: Path) -> None:
    # 3.0.0이 버전은 더 높지만 스킬이 없다 — 실존하는 2.0.0을 골라야 한다
    _make_version(tmp_path, "3.0.0", with_skill=False)
    fallback = _make_version(tmp_path, "2.0.0")

    result = rehome_upstream(_dead(tmp_path, "2.0.0-rc.1"))

    assert result == fallback


def test_contract4_returns_none_when_evaporated(tmp_path: Path) -> None:
    (tmp_path / "cache" / "mkt" / "plug").mkdir(parents=True)

    assert rehome_upstream(_dead(tmp_path, "2.0.0-rc.1")) is None


def test_contract5_hidden_dirs_are_not_candidates(tmp_path: Path) -> None:
    _make_version(tmp_path, ".backup")

    assert rehome_upstream(_dead(tmp_path, "2.0.0-rc.1")) is None
