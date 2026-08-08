output "artifact_registry_repository" {
  value = google_artifact_registry_repository.backend.id
}

output "api_service_name" {
  value = try(google_cloud_run_v2_service.api[0].name, null)
}

output "api_url" {
  value = try(google_cloud_run_v2_service.api[0].uri, null)
}

output "migration_job_name" {
  value = try(google_cloud_run_v2_job.migration[0].name, null)
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  value = google_service_account.deployer.email
}

output "neon_project_id" {
  value = neon_project.staging.id
}

output "neon_default_branch_id" {
  value = neon_project.staging.default_branch_id
}

output "vercel_project_id" {
  value = vercel_project.web.id
}

output "vercel_staging_environment_id" {
  value = vercel_custom_environment.staging.id
}

output "required_secret_names" {
  value = values(local.secret_ids)
}
