"""Smoke test: the package installs, imports and reports a version."""

import sys

import rcm


def test_package_imports_and_has_version() -> None:
    assert isinstance(rcm.__version__, str)
    assert rcm.__version__


def test_runs_on_python_312() -> None:
    assert sys.version_info[:2] == (3, 12)
