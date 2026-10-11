"""Hidden grader for terraform-s3-hardening (structural checks via python-hcl2).

One requirement per test, so the pytest summary gives partial credit.
"""
import pytest

import tfgrader
from tfgrader import first_block, ref, resources

PAB_SETTINGS = ("block_public_acls", "block_public_policy",
                "ignore_public_acls", "restrict_public_buckets")


def is_true(value) -> bool:
    return value is True or str(value).lower() == "true"


def single(module, rtype) -> dict:
    found = resources(module, rtype)
    assert found, f"no {rtype} resource in modules/s3_bucket"
    assert len(found) == 1, f"expected one {rtype}, got {list(found)}"
    return next(iter(found.values()))


def test_all_tf_files_parse(target_dir):
    files = [p for p in target_dir.rglob("*.tf") if ".terraform" not in p.parts]
    assert files
    for path in files:
        tfgrader.parse_file(path)  # raises on invalid HCL


def test_root_module_unchanged(root):
    mod = tfgrader.blocks(root, "module").get("audit_logs")
    assert mod, "module \"audit_logs\" is missing from the root module"
    assert mod["source"] == "./modules/s3_bucket"
    assert mod["bucket_name"] == "example-corp-audit-logs"


def test_module_interface_unchanged(module):
    assert {"bucket_name", "tags"} <= set(tfgrader.blocks(module, "variable"))
    outputs = tfgrader.blocks(module, "output")
    assert {"bucket_id", "bucket_arn"} <= set(outputs)


def test_bucket_still_named_by_variable(module, bucket_name):
    body = resources(module, "aws_s3_bucket")[bucket_name]
    assert ref(body.get("bucket")) == "var.bucket_name"


def test_no_deprecated_inline_blocks(module, bucket_name):
    body = resources(module, "aws_s3_bucket")[bucket_name]
    deprecated = {"versioning", "server_side_encryption_configuration", "acl"} & set(body)
    assert not deprecated, f"deprecated inline arguments on aws_s3_bucket: {sorted(deprecated)}"


def test_versioning_enabled(module):
    body = single(module, "aws_s3_bucket_versioning")
    assert first_block(body, "versioning_configuration").get("status") == "Enabled"


def test_sse_kms(module):
    body = single(module, "aws_s3_bucket_server_side_encryption_configuration")
    default = first_block(first_block(body, "rule"), "apply_server_side_encryption_by_default")
    assert default.get("sse_algorithm") == "aws:kms"


def test_bucket_key_enabled(module):
    # Easy to miss: bucket_key_enabled belongs on `rule`, not inside
    # apply_server_side_encryption_by_default.
    body = single(module, "aws_s3_bucket_server_side_encryption_configuration")
    assert is_true(first_block(body, "rule").get("bucket_key_enabled"))


@pytest.mark.parametrize("setting", PAB_SETTINGS)
def test_public_access_block(module, setting):
    body = single(module, "aws_s3_bucket_public_access_block")
    assert is_true(body.get(setting)), f"{setting} must be true"


@pytest.mark.parametrize("rtype", [
    "aws_s3_bucket_versioning",
    "aws_s3_bucket_server_side_encryption_configuration",
    "aws_s3_bucket_public_access_block",
])
def test_settings_attached_to_module_bucket(module, bucket_name, rtype):
    body = single(module, rtype)
    assert ref(body.get("bucket")) in (f"aws_s3_bucket.{bucket_name}.id",
                                      f"aws_s3_bucket.{bucket_name}.bucket")
