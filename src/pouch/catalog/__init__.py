"""pouch 도구 카탈로그 — 무엇을 담을 수 있는지의 레지스트리.

ownership 3값(owned/vendored/linked)으로 "pouch와 도구의 관계"를 1급으로 표현한다.
"""

from __future__ import annotations

from pouch.catalog.model import Overlay, Ownership, ToolEntry, ToolKind
from pouch.catalog.store import CatalogStore

__all__ = ["CatalogStore", "Overlay", "Ownership", "ToolEntry", "ToolKind"]
