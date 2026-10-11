# Harden the shared S3 bucket module

A security review flagged our shared Terraform module `modules/s3_bucket`, which the
root module uses for the audit-log bucket. Change the module so that **every bucket it
creates**:

1. has **versioning enabled**;
2. is **encrypted at rest with SSE-KMS** (`aws:kms`) using the AWS-managed key, with
   **S3 Bucket Keys enabled** to reduce KMS costs;
3. **blocks all public access**: all four public access block settings must be on.

Constraints:

- We are on AWS provider v5. Use the standalone resources it recommends for these
  settings, not the deprecated inline blocks on `aws_s3_bucket`.
- Do not change the module's inputs (`bucket_name`, `tags`) or outputs (`bucket_id`,
  `bucket_arn`), and do not change the root module (`main.tf`, `providers.tf`).
- The configuration must pass `tofu validate` (OpenTofu is installed; `terraform` is
  an alias for it). You do not have AWS credentials, so do not run `plan` or `apply`.
