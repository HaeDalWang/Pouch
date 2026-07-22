"""규칙(rule)을 표면에 되돌려놓기 — 접었던 폴더를 다시 편다.

배승도 락(2026-07-22): "기존에 사용중이던 claude의 Rule을 pouch가 저장? 해야하는데
원래는 디렉토리 트리가 아니라 _ 로 구분을 했었고 대신 이렇게 하면 다시 돌려놓을떄
보고 다시 디렉토리 단위로 쪼개야하니까 헷갈리잔아?? 그래서 절차가 하나 더 생기지만
그게 거짓말을 하는건 아니니까 '가'을 추천한다 이거잔아??? 나도 그래 맞아 '가'로 하자구"

훑기·들이기는 되는데 표면에 올릴 자리가 없어 `catalog install`이 거절하던 반쪽을
닫는다. 내려놓는 자리가 주워온 자리와 같아야 왕복이 어긋나지 않는다.
"""

from __future__ import annotations

import frontmatter

from pouch.catalog.docid import fold_rule_id, unfold_rule_id
from pouch.catalog.install import install_doc_file, target_path_for
from pouch.catalog.model import ToolEntry, ToolKind


def _rule(entry_id: str, body: str = "# 규칙 본문\n") -> ToolEntry:
    return ToolEntry.owned(
        id=entry_id,
        kind=ToolKind.RULE,
        source="test",
        title=entry_id,
        description="설명",
        body=body,
    )


# --- 접기 ↔ 펴기 (한 곳에서 두 방향) ---


def test_folding_and_unfolding_a_rule_id_round_trips() -> None:
    """들일 때 접은 이름을, 올릴 때 그대로 되편다."""
    folded = fold_rule_id("python", "coding-style")

    assert folded == "python__coding-style"
    assert unfold_rule_id(folded) == ("python", "coding-style")


def test_an_unfolded_id_without_a_fold_mark_is_just_a_name() -> None:
    """접은 자국이 없으면 폴더 없이 이름 하나 — 지어내지 않는다."""
    assert unfold_rule_id("solo") == ("solo",)


def test_only_the_first_fold_mark_is_a_folder_boundary() -> None:
    """이름 자체에 `__`가 있던 규칙도 원래 이름을 잃지 않는다."""
    assert unfold_rule_id("common__a__b") == ("common", "a__b")


# --- 표면 자리 ---


def test_rule_goes_back_into_its_original_folder(tmp_path) -> None:
    """`python__coding-style` → `rules/python/coding-style.md`."""
    assert target_path_for(_rule("python__coding-style"), base=tmp_path) == (
        tmp_path / "rules" / "python" / "coding-style.md"
    )


def test_a_rule_without_a_folder_lands_flat(tmp_path) -> None:
    assert target_path_for(_rule("standalone"), base=tmp_path) == (
        tmp_path / "rules" / "standalone.md"
    )


def test_installing_a_rule_writes_the_body(tmp_path) -> None:
    written = install_doc_file(_rule("golang__testing", "# Go 테스트\n"), base=tmp_path)

    assert written == tmp_path / "rules" / "golang" / "testing.md"
    assert "# Go 테스트" in written.read_text(encoding="utf-8")


def test_an_installed_rule_carries_no_frontmatter(tmp_path) -> None:
    """규칙 파일은 하네스가 평문으로 통째로 읽는다 — 머리말을 얹으면 그 글자가
    지침 안에 그대로 섞여 들어간다. 원래 모습대로 본문만 쓴다."""
    written = install_doc_file(_rule("python__patterns"), base=tmp_path)

    text = written.read_text(encoding="utf-8")
    assert not text.startswith("---")
    assert frontmatter.loads(text).metadata == {}


def test_an_installed_rule_ends_with_a_newline(tmp_path) -> None:
    """원래 모습대로 — 본문을 뽑는 과정에서 벗겨지던 끝 개행을 되돌려놓는다."""
    written = install_doc_file(_rule("golang__style", "# 제목\n\n- 항목"), base=tmp_path)

    assert written.read_text(encoding="utf-8").endswith("\n")


def test_two_rules_with_the_same_name_do_not_collide_on_the_surface(tmp_path) -> None:
    """`coding-style`이 여러 묶음에 겹쳐도 각자 제 폴더로 간다(겹침이 이 접기의 이유)."""
    a = install_doc_file(_rule("python__coding-style", "# 파이썬\n"), base=tmp_path)
    b = install_doc_file(_rule("common__coding-style", "# 공통\n"), base=tmp_path)

    assert a != b
    assert "# 파이썬" in a.read_text(encoding="utf-8")
    assert "# 공통" in b.read_text(encoding="utf-8")
