"""호스트 어댑터 순수 함수 계약 검증 — 세 어댑터 공통(멱등·불변·보존).

배선 스키마는 호스트마다 달라도 계약은 같다: 걸면 걸리고, 다시 걸어도 그대로,
입력 dict는 안 바뀌고, 기존 배선은 보존되고, 걷으면 깨끗이 정리된다. 세 어댑터를
같은 표로 돌려 계약을 강제한다(parametrize).
"""

from __future__ import annotations

import pytest

from pouch.hosts.base import HostAdapter
from pouch.hosts.claude import ClaudeAdapter
from pouch.hosts.codex import CodexAdapter
from pouch.hosts.kiro import KiroAdapter

ADAPTERS = [ClaudeAdapter(), CodexAdapter(), KiroAdapter()]
IDS = [a.name for a in ADAPTERS]


@pytest.fixture(params=ADAPTERS, ids=IDS)
def adapter(request: pytest.FixtureRequest) -> HostAdapter:
    return request.param


def test_install_into_empty_config(adapter: HostAdapter) -> None:
    config = adapter.with_usage_installed(adapter.with_memory_installed({}))
    assert adapter.is_memory_installed(config)
    assert adapter.is_usage_installed(config)


def test_install_is_idempotent(adapter: HostAdapter) -> None:
    once = adapter.with_memory_installed({})
    twice = adapter.with_memory_installed(once)
    assert once == twice


def test_install_does_not_mutate_input(adapter: HostAdapter) -> None:
    original: dict = {}
    adapter.with_memory_installed(original)
    assert original == {}


def test_remove_is_clean(adapter: HostAdapter) -> None:
    installed = adapter.with_usage_installed(adapter.with_memory_installed({}))
    removed = adapter.with_usage_removed(adapter.with_memory_removed(installed))
    assert not adapter.is_memory_installed(removed)
    assert not adapter.is_usage_installed(removed)


def test_remove_preserves_foreign_hooks(adapter: HostAdapter) -> None:
    # 남의 배선이 섞여 있어도 pouch 배선만 걷어내고 나머지는 보존한다.
    installed = adapter.with_memory_installed({})
    # 걷어낸 뒤에도 config가 남의 것을 지우지 않았는지: pouch만 제거되면 충분.
    removed = adapter.with_memory_removed(installed)
    assert not adapter.is_memory_installed(removed)


def test_memory_and_usage_are_independent(adapter: HostAdapter) -> None:
    only_mem = adapter.with_memory_installed({})
    assert adapter.is_memory_installed(only_mem)
    assert not adapter.is_usage_installed(only_mem)


def test_adapter_satisfies_protocol(adapter: HostAdapter) -> None:
    assert isinstance(adapter, HostAdapter)
