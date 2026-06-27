"""pouch — your own otter's pouch of tools. One day, a whole raft of them."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pouch")
except PackageNotFoundError:  # 설치 전(소스 직접 실행) 폴백
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
