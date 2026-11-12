"""Regression suite for Mondeora-Drop-System. Offline only: no live eBay/AliExpress calls, no writes
to data/dropshipping.db. Run: "C:/Program Files/Python311/python.exe" -m pytest tests -q"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import runtime  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_latch():
    runtime._forced_read_only = False
    yield
    runtime._forced_read_only = False


def py_files():
    skip = ('venv', 'node_modules', '.git', '__pycache__', '_archive')
    return [p for p in ROOT.rglob('*.py') if not any(s in p.parts for s in skip)]
