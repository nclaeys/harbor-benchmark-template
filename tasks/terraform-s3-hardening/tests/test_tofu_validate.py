"""Validity check: the answer must pass `tofu validate` (real provider schema).

Inside the task image this always runs (OpenTofu + offline provider mirror).
When grading locally without tofu/terraform, or without network to fetch the
provider, the test is skipped instead of failed; the structural tests still run.
"""
import pytest

import tfgrader


def test_tofu_validate(target_dir):
    if tfgrader.tf_binary() is None:
        pytest.skip("no tofu/terraform binary on PATH (runs inside the task image)")
    ok, output = tfgrader.validate(target_dir)
    if not ok and tfgrader.is_provider_install_failure(output):
        pytest.skip("providers could not be installed:\n" + output)
    assert ok, f"tofu validate failed:\n{output}"
