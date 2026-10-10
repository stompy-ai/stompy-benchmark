"""Trusted bootstrap: ignore submitted pytest configuration and conftests."""

import sys

import pytest

sys.path.insert(0, "/submission")
# Pin the plugin to the submitted source without adding its tests to sys.path.
import importlib.util
from pathlib import Path

pkg = Path("/submission/stompy-admin/stompy_admin")
spec = importlib.util.spec_from_file_location(
    "stompy_admin", pkg / "__init__.py", submodule_search_locations=[str(pkg)]
)
m = importlib.util.module_from_spec(spec)
sys.modules["stompy_admin"] = m
spec.loader.exec_module(m)
raise SystemExit(
    pytest.main(
        [
            "-c",
            "/oracle/pytest.ini",
            "--confcutdir=/oracle",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "--junitxml=/evidence/junit.xml",
            "/oracle/test_lifecycle_rest.py",
            "-q",
            "--tb=short",
        ]
    )
)
