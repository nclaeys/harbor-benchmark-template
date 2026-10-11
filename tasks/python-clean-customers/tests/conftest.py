"""Grader bootstrap: run the candidate's script and expose its output.

The directory being graded comes from $BENCH_TARGET (set to /app by test.sh
inside Harbor; set to a temp copy by scripts/validate_tasks.py locally).
"""
import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def target_dir() -> Path:
    return Path(os.environ.get("BENCH_TARGET", "/app")).resolve()


def run_clean(input_csv: Path, output_csv: Path) -> list[dict]:
    """Run clean_customers.py as the instruction describes and parse its output."""
    proc = subprocess.run(
        [sys.executable, "clean_customers.py", str(input_csv), str(output_csv)],
        cwd=target_dir(), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"script failed:\n{proc.stdout}\n{proc.stderr}"
    assert output_csv.exists(), "script did not write the output file"
    with output_csv.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def output_header(rows) -> list[str]:
    return list(rows[0].keys()) if rows else []


@pytest.fixture(scope="session")
def rows(tmp_path_factory) -> list[dict]:
    # The output dir does not exist yet: the script must create it.
    out = tmp_path_factory.mktemp("out") / "nested" / "customers_clean.csv"
    return run_clean(target_dir() / "data" / "customers_raw.csv", out)


@pytest.fixture(scope="session")
def by_id(rows) -> dict[str, dict]:
    return {r["customer_id"]: r for r in rows}


@pytest.fixture(scope="session")
def hidden_rows(tmp_path_factory) -> list[dict]:
    out = tmp_path_factory.mktemp("hidden") / "customers_clean.csv"
    return run_clean(FIXTURES / "hidden_customers.csv", out)
