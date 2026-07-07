"""시작 세트 모델 계약 — 세트 파일을 읽고, 역할·스택 토큰으로 고른다.

세트 = 가리키는 목록(선곡표). 항목마다 "어디서 가져올지(source)"와
"무엇을 표면에 올릴지(install)"를 담는다 — 빈 카탈로그(콜드 스타트)를
실제로 채우기 위해 출처까지 담는다(배승도 결정, 2026-07-07).

  ① 세트 JSON 파일 하나 → StarterSet (이름·제목·매칭 토큰·항목들)
  ② available_sets: 내장 폴더 + 사용자 폴더(~/.pouch/sets/)를 합쳐 읽는다
  ③ 같은 이름이면 사용자 세트가 내장을 이긴다 (개인 우선 원칙)
  ④ match_sets: 관심 토큰과 겹치는 세트만, 겹침 많은 순으로
  ⑤ 깨진 세트 파일은 건너뛴다 (한 파일이 전체를 인질로 잡지 않음)
"""

from __future__ import annotations

import json
from pathlib import Path

from pouch.sets.model import StarterSet, available_sets, load_set_file, match_sets


def _write_set(directory: Path, name: str, *, match: list[str], title: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(
        json.dumps({
            "name": name,
            "title": title or name,
            "description": "테스트 세트",
            "match": match,
            "items": [{"source": "~/nowhere", "install": ["a", "b"]}],
        }),
        encoding="utf-8",
    )
    return path


def test_contract1_load_set_file(tmp_path: Path) -> None:
    path = _write_set(tmp_path, "demo", match=["aws", "devops"], title="데모 세트")

    loaded = load_set_file(path)

    assert loaded.name == "demo"
    assert loaded.title == "데모 세트"
    assert loaded.match_tokens == ("aws", "devops")
    assert loaded.items[0].source == "~/nowhere"
    assert loaded.items[0].install == ("a", "b")


def test_contract2_available_merges_builtin_and_user(tmp_path: Path) -> None:
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    _write_set(builtin, "base-set", match=["aws"])
    _write_set(user, "my-set", match=["go"])

    sets = available_sets(builtin_dir=builtin, user_dir=user)

    assert {s.name for s in sets} == {"base-set", "my-set"}


def test_contract3_user_set_overrides_builtin_same_name(tmp_path: Path) -> None:
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    _write_set(builtin, "same", match=["aws"], title="내장판")
    _write_set(user, "same", match=["aws"], title="사용자판")

    sets = available_sets(builtin_dir=builtin, user_dir=user)

    assert len(sets) == 1
    assert sets[0].title == "사용자판"  # 개인 우선


def test_contract4_match_by_token_overlap_ranked(tmp_path: Path) -> None:
    aws_devops = load_set_file(_write_set(tmp_path / "a", "aws-devops", match=["aws", "devops"]))
    go_only = load_set_file(_write_set(tmp_path / "b", "go-only", match=["go"]))
    web = load_set_file(_write_set(tmp_path / "c", "web", match=["react"]))

    matched = match_sets([go_only, web, aws_devops], tokens={"devops", "aws", "python"})

    # 겹침 2개(aws-devops)만 매칭 — go·react는 관심 밖
    assert [s.name for s in matched] == ["aws-devops"]


def test_contract5_broken_set_file_is_skipped(tmp_path: Path) -> None:
    user = tmp_path / "user"
    _write_set(user, "good", match=["aws"])
    user.joinpath("broken.json").write_text("{ not json", encoding="utf-8")

    sets = available_sets(builtin_dir=tmp_path / "none", user_dir=user)

    assert [s.name for s in sets] == ["good"]
