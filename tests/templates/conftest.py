"""Conftest for template snapshot tests."""

from __future__ import annotations


def pytest_addoption(parser):
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Regenerate golden snapshot files",
    )
