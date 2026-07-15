"""adopt — 네이티브 메모리 이관: 순수 코어(스코프·계층·이름) + CLI 통합."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pouch.memory.adopt import (
    AdoptionItem,
    SkippedNative,
    partition_existing,
    plan_native_file,
)
from pouch.memory.commands import app
from pouch.memory.model import MemoryEntry, MemoryScope, MemoryState, MemoryType

runner = CliRunner()


def _native(
    mem_type: str | None,
    *,
    name: str = "",
    description: str = "d",
    body: str = "본문",
    nested: bool = True,
) -> str:
    """네이티브(Claude 기본) 메모리 파일 텍스트를 만든다."""
    lines = ["---"]
    if name:
        lines.append(f'name: "{name}"')
    lines.append(f'description: "{description}"')
    if mem_type is not None:
        if nested:
            lines += ["metadata:", "  node_type: memory", f"  type: {mem_type}", "  originSessionId: abc-123"]
        else:
            lines.append(f"type: {mem_type}")
    lines += ["---", "", body, ""]
    return "\n".join(lines)


def _plan(text: str, *, stem: str = "stem", created: date = date(2026, 6, 1)):
    return plan_native_file(text, source_path=f"/n/{stem}.md", stem=stem, created=created)


# ── 스코프·계층: 타입이 자리와 계층을 정한다 ──────────────────────────────


def test_feedback_goes_global_indexed() -> None:
    item = _plan(_native("feedback", name="respect-stop"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.type is MemoryType.FEEDBACK
    assert item.entry.scope is MemoryScope.GLOBAL
    assert item.entry.state is MemoryState.INDEXED


def test_user_goes_global_indexed() -> None:
    item = _plan(_native("user"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.scope is MemoryScope.GLOBAL
    assert item.entry.state is MemoryState.INDEXED


def test_reference_goes_project_indexed() -> None:
    item = _plan(_native("reference"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.scope is MemoryScope.PROJECT
    assert item.entry.state is MemoryState.INDEXED


def test_project_goes_project_pending() -> None:
    """네이티브가 어긴 '안정 핵심만 주입' 복원 — 날짜 없는 세션 맥락은 리뷰 대기(주입 안 함)."""
    item = _plan(_native("project"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.scope is MemoryScope.PROJECT
    assert item.entry.state is MemoryState.PENDING


def test_project_dated_name_goes_archived() -> None:
    # 날짜(YYMMDD) 박힌 project = 명백한 세션로그 → ARCHIVED(주입 X·recall O·리뷰 잔소리 없음).
    item = _plan(_native("project"), stem="project_full_review_260710")
    assert isinstance(item, AdoptionItem)
    assert item.entry.name == "full_review_260710"
    assert item.entry.state is MemoryState.ARCHIVED


def test_project_undated_milestone_stays_pending() -> None:
    # 날짜 없는 활성 마일스톤은 PENDING 유지(리뷰 후 promote 대상).
    item = _plan(_native("project", name="v10-inverse-reenablement"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.state is MemoryState.PENDING


def test_dated_heuristic_rejects_invalid_month() -> None:
    # "121314"는 월(13)이 유효하지 않아 날짜로 안 봄 → 이슈번호 오탐 방지, PENDING 유지.
    item = _plan(_native("project", name="issues-121314-fix"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.state is MemoryState.PENDING


# ── 파싱·건너뜀 ──────────────────────────────────────────────────────────


def test_flat_type_fallback() -> None:
    item = _plan(_native("feedback", nested=False))
    assert isinstance(item, AdoptionItem)
    assert item.entry.type is MemoryType.FEEDBACK


def test_unknown_type_skipped() -> None:
    # boundary는 네이티브에 없는 타입 → 조용히 삼키지 않고 이유와 함께 건너뜀.
    result = _plan(_native("boundary"))
    assert isinstance(result, SkippedNative)
    assert "boundary" in result.reason


def test_missing_type_skipped() -> None:
    result = _plan(_native(None))
    assert isinstance(result, SkippedNative)


def test_broken_frontmatter_skipped_not_crash() -> None:
    # 실데이터 회귀: description에 따옴표 없는 콜론이 있으면 YAML이 터진다.
    # 전체 이관을 멈추지 않고 이 파일만 건너뛴다.
    broken = "---\ndescription: 대시보드: 503 원인\nmetadata:\n  type: reference\n---\n본문\n"
    result = _plan(broken)
    assert isinstance(result, SkippedNative)
    assert "파싱 실패" in result.reason


# ── 이름 파생 ────────────────────────────────────────────────────────────


def test_name_prefers_frontmatter() -> None:
    item = _plan(_native("feedback", name="respect-stop-here"), stem="feedback_respect_stop_here")
    assert isinstance(item, AdoptionItem)
    assert item.entry.name == "respect-stop-here"


def test_name_falls_back_to_stem_stripping_type_prefix() -> None:
    item = _plan(_native("project"), stem="project_edge_hunt_260714")
    assert isinstance(item, AdoptionItem)
    assert item.entry.name == "edge_hunt_260714"


def test_name_strips_type_prefix_from_frontmatter_too() -> None:
    # frontmatter name에 타입 접두가 박혀 있어도 벗긴다(타입은 이미 필드).
    item = _plan(_native("feedback", name="feedback_guard_runs"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.name == "guard_runs"


def test_name_prefix_strip_avoids_false_match() -> None:
    # 접두 뒤에 _가 올 때만 벗긴다 — "projection"은 "project_"로 시작하지 않는다.
    item = _plan(_native("project", name="projection_model"))
    assert isinstance(item, AdoptionItem)
    assert item.entry.name == "projection_model"


def test_name_sanitizes_unsafe_chars() -> None:
    item = _plan(_native("user", name="weird name/with:chars"))
    assert isinstance(item, AdoptionItem)
    assert "/" not in item.entry.name
    assert ":" not in item.entry.name


def test_created_and_body_preserved() -> None:
    item = _plan(_native("reference", description="설명", body="본문 내용"), created=date(2026, 3, 3))
    assert isinstance(item, AdoptionItem)
    assert item.entry.created == date(2026, 3, 3)
    assert item.entry.description == "설명"
    assert "본문 내용" in item.entry.body


def test_empty_description_becomes_empty_string_not_none() -> None:
    # 빈 description(YAML None)이 문자열 "None"으로 저장되지 않는다.
    text = "---\nname: x\ndescription:\nmetadata:\n  type: user\n---\n본문\n"
    item = _plan(text)
    assert isinstance(item, AdoptionItem)
    assert item.entry.description == ""


# ── 덮어쓰기 방지(partition_existing) ────────────────────────────────────


def _item(name: str, scope: MemoryScope = MemoryScope.GLOBAL) -> AdoptionItem:
    return AdoptionItem(
        entry=MemoryEntry(name=name, description="d", body="b", type=MemoryType.USER, scope=scope),
        source_path=f"/n/{name}.md",
        reason="r",
    )


def test_partition_skips_existing_pouch_memory() -> None:
    kept, skipped = partition_existing(
        [_item("a"), _item("b")], existing={("a", MemoryScope.GLOBAL)}
    )
    assert [i.entry.name for i in kept] == ["b"]
    assert len(skipped) == 1
    assert "이미 pouch에 있음" in skipped[0].reason


def test_partition_dedups_within_batch() -> None:
    kept, skipped = partition_existing([_item("a"), _item("a")], existing=set())
    assert [i.entry.name for i in kept] == ["a"]
    assert len(skipped) == 1
    assert "배치 내" in skipped[0].reason


def test_partition_same_name_different_scope_both_kept() -> None:
    kept, skipped = partition_existing(
        [_item("a", MemoryScope.GLOBAL), _item("a", MemoryScope.PROJECT)], existing=set()
    )
    assert len(kept) == 2
    assert skipped == []


# ── CLI 통합 ─────────────────────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """글로벌은 POUCH_HOME으로, 프로젝트는 .git 있는 cwd로 격리한다."""
    monkeypatch.setenv("POUCH_HOME", str(tmp_path / "global"))
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    return tmp_path


def _seed_native(project: Path) -> Path:
    from pouch import paths

    native = paths.claude_project_memory_dir(project)
    native.mkdir(parents=True)
    (native / "feedback_stop.md").write_text(
        _native("feedback", name="stop-here"), encoding="utf-8"
    )
    # 날짜 없는 project → PENDING(리뷰 대기). 날짜 박힌 세션로그의 ARCHIVED 경로는
    # 별도 단위 테스트가 커버한다.
    (native / "project_trading_scope.md").write_text(_native("project"), encoding="utf-8")
    (native / "MEMORY.md").write_text("- 인덱스 줄(이관 대상 아님)\n", encoding="utf-8")
    return native


def test_adopt_migrates_by_type(workspace: Path) -> None:
    from pouch.memory.store import MemoryStore

    project = workspace / "proj"
    _seed_native(project)

    result = runner.invoke(app, ["adopt"])
    assert result.exit_code == 0, result.stdout

    entries = {e.name: e for e in MemoryStore(project_dir=project / ".pouch" / "memory").list()}
    assert entries["stop-here"].scope is MemoryScope.GLOBAL
    assert entries["stop-here"].state is MemoryState.INDEXED
    assert entries["trading_scope"].scope is MemoryScope.PROJECT
    assert entries["trading_scope"].state is MemoryState.PENDING
    # MEMORY.md 인덱스는 이관되지 않는다.
    assert "trading_scope" in entries and "MEMORY" not in entries


def test_adopt_default_keeps_native(workspace: Path) -> None:
    # 기본은 옮기기만 — 네이티브 자동로드는 안전망으로 남긴다(끄지 않음).
    from pouch import paths
    from pouch.hooks.settings import is_native_memory_disabled, load_settings

    _seed_native(workspace / "proj")
    result = runner.invoke(app, ["adopt"])
    assert result.exit_code == 0, result.stdout
    assert not is_native_memory_disabled(load_settings(paths.claude_settings_path()))


def test_adopt_disable_native_flag_turns_off(workspace: Path) -> None:
    # --disable-native를 명시해야 네이티브 자동로드를 끈다(대체 확정).
    from pouch import paths
    from pouch.hooks.settings import is_native_memory_disabled, load_settings

    _seed_native(workspace / "proj")
    result = runner.invoke(app, ["adopt", "--disable-native"])
    assert result.exit_code == 0, result.stdout
    assert is_native_memory_disabled(load_settings(paths.claude_settings_path()))


def test_adopt_dry_run_writes_nothing(workspace: Path) -> None:
    from pouch import paths
    from pouch.hooks.settings import is_native_memory_disabled, load_settings
    from pouch.memory.store import MemoryStore

    project = workspace / "proj"
    _seed_native(project)

    result = runner.invoke(app, ["adopt", "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "stop-here" in result.stdout  # 계획에 이름이 보인다

    assert list(MemoryStore(project_dir=project / ".pouch" / "memory").list()) == []
    assert not is_native_memory_disabled(load_settings(paths.claude_settings_path()))


def test_adopt_no_disable_keeps_native(workspace: Path) -> None:
    from pouch import paths
    from pouch.hooks.settings import is_native_memory_disabled, load_settings

    project = workspace / "proj"
    _seed_native(project)

    result = runner.invoke(app, ["adopt", "--no-disable-native"])
    assert result.exit_code == 0, result.stdout
    assert not is_native_memory_disabled(load_settings(paths.claude_settings_path()))


def test_adopt_no_native_dir_exits_cleanly(workspace: Path) -> None:
    # 네이티브 메모리 디렉토리가 없으면 조용히 종료(에러 아님).
    result = runner.invoke(app, ["adopt"])
    assert result.exit_code == 0, result.stdout
    assert "없습니다" in result.stdout


def test_adopt_rerun_does_not_reset_promoted(workspace: Path) -> None:
    # #1 회귀: 재실행이 사용자가 promote한 상태를 PENDING으로 되돌리지 않는다.
    from pouch.memory.store import MemoryStore

    project = workspace / "proj"
    _seed_native(project)
    runner.invoke(app, ["adopt"])  # 1차: project 기억은 PENDING

    store = MemoryStore(project_dir=project / ".pouch" / "memory")
    store.promote(store.get("trading_scope", MemoryScope.PROJECT))
    assert store.get("trading_scope", MemoryScope.PROJECT).state is MemoryState.INDEXED

    result = runner.invoke(app, ["adopt"])  # 2차
    assert result.exit_code == 0, result.stdout
    assert store.get("trading_scope", MemoryScope.PROJECT).state is MemoryState.INDEXED


def test_adopt_does_not_overwrite_existing_pouch_memory(workspace: Path) -> None:
    # #1 회귀: native 이름이 기존 pouch 기억과 겹쳐도 기존 것을 덮지 않는다.
    from pouch.memory.store import MemoryStore

    project = workspace / "proj"
    _seed_native(project)
    store = MemoryStore(project_dir=project / ".pouch" / "memory")
    store.save(
        MemoryEntry(
            name="stop-here", description="내 것", body="원래 내용",
            type=MemoryType.FEEDBACK, scope=MemoryScope.GLOBAL,
        )
    )

    result = runner.invoke(app, ["adopt"])
    assert result.exit_code == 0, result.stdout
    assert store.get("stop-here", MemoryScope.GLOBAL).body == "원래 내용"  # 안 덮임


def test_adopt_from_path_reads_that_project(workspace: Path) -> None:
    # #2 회귀: --from으로 다른(서브디렉토리 등) 프로젝트의 네이티브를 이관한다.
    from pouch.memory.store import MemoryStore

    other = workspace / "other"
    (other / ".git").mkdir(parents=True)
    _seed_native(other)

    result = runner.invoke(app, ["adopt", "--from", str(other), "--no-disable-native"])
    assert result.exit_code == 0, result.stdout

    names = {e.name for e in MemoryStore(project_dir=other / ".pouch" / "memory").list()}
    assert "stop-here" in names
    assert "trading_scope" in names
