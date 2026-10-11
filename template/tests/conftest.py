"""Grader bootstrap. The directory being graded comes from $BENCH_TARGET
(/app inside Harbor, a temp copy when running scripts/validate_tasks.py)."""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def target_dir() -> Path:
    return Path(os.environ.get("BENCH_TARGET", "/app")).resolve()
