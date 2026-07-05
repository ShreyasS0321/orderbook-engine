"""Smoke test: the package imports and exposes its version."""

import orderbook


def test_package_imports() -> None:
    assert isinstance(orderbook.__version__, str)
    assert orderbook.__version__
