module "audit_logs" {
  source = "./modules/s3_bucket"

  bucket_name = "example-corp-audit-logs"
  tags = {
    team    = "platform"
    purpose = "audit-logs"
  }
}

output "audit_logs_bucket_arn" {
  value = module.audit_logs.bucket_arn
}
