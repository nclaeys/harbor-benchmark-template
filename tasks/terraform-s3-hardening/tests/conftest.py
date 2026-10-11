"""Grader bootstrap: parse the candidate's Terraform.

The directory being graded comes from $BENCH_TARGET (set to /app by test.sh
inside Harbor; set to a temp copy by scripts/validate_tasks.py locally).
"""
import os
from pathlib import Path

import pytest

import tfgrader


@pytest.fixture(scope="session")
def target_dir() -> Path:
    return Path(os.environ.get("BENCH_TARGET", "/app")).resolve()


@pytest.fixture(scope="session")
def root(target_dir) -> list[dict]:
    return tfgrader.parse_module(target_dir)


@pytest.fixture(scope="session")
def module(target_dir) -> list[dict]:
    return tfgrader.parse_module(target_dir / "modules" / "s3_bucket")


@pytest.fixture(scope="session")
def bucket_name(module) -> str:
    buckets = tfgrader.resources(module, "aws_s3_bucket")
    assert len(buckets) == 1, f"expected exactly one aws_s3_bucket, got {list(buckets)}"
    return next(iter(buckets))
