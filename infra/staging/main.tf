locals {
  name_prefix = "tradearena-staging"
  labels = {
    application = "tradearena"
    environment = "staging"
    managed_by  = "terraform"
  }
  secret_ids = {
    database_url           = "tradearena-staging-database-url"
    bff_shared_secret      = "tradearena-staging-bff-shared-secret"
    auth0_client_secret    = "tradearena-staging-auth0-client-secret"
    session_encryption_key = "tradearena-staging-session-encryption-key"
  }
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sts.googleapis.com",
    "cloudscheduler.googleapis.com",
  ])

  project            = var.gcp_project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "backend" {
  location      = var.gcp_region
  repository_id = "tradearena"
  description   = "Imágenes canónicas de API y migraciones de TradeArena"
  format        = "DOCKER"
  labels        = local.labels

  depends_on = [google_project_service.required]
}

resource "google_service_account" "api" {
  account_id   = "tradearena-api-stg"
  display_name = "TradeArena API staging"
}

resource "google_service_account" "migration" {
  account_id   = "tradearena-migrate-stg"
  display_name = "TradeArena migrations staging"
}

resource "google_service_account" "deployer" {
  account_id   = "tradearena-deploy-stg"
  display_name = "GitHub Actions staging deployer"
}

resource "google_service_account" "scheduler" {
  account_id   = "tradearena-scheduler-stg"
  display_name = "Cloud Scheduler staging (sin targets en TA-039)"
}

resource "google_secret_manager_secret" "runtime" {
  for_each = local.secret_ids

  secret_id = each.value
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "api_database" {
  secret_id = google_secret_manager_secret.runtime["database_url"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_bff" {
  secret_id = google_secret_manager_secret.runtime["bff_shared_secret"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "migration_database" {
  secret_id = google_secret_manager_secret.runtime["database_url"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.migration.email}"
}

resource "google_cloud_run_v2_service" "api" {
  count = var.deploy_runtime ? 1 : 0

  name                = "tradearena-api-staging"
  location            = var.gcp_region
  deletion_protection = var.cloud_run_deletion_protection
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.labels

  template {
    service_account = google_service_account.api.email
    timeout         = "60s"

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.api_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "AUTH0_DOMAIN"
        value = var.auth0_domain
      }
      env {
        name  = "AUTH0_CLIENT_ID"
        value = var.auth0_client_id
      }
      env {
        name  = "MARKET_DATA_PROVIDER"
        value = "fixture"
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime["database_url"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "BFF_SHARED_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime["bff_shared_secret"].secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        failure_threshold     = 12
        initial_delay_seconds = 2
        period_seconds        = 5
        timeout_seconds       = 2

        http_get {
          path = "/health/live"
          port = 8080
        }
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.api_database,
    google_secret_manager_secret_iam_member.api_bff,
  ]

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

# Cloud Run queda alcanzable desde el BFF de Vercel. La autorización de datos
# sigue en FastAPI mediante sesión opaca y secreto BFF; PostgreSQL nunca es público.
resource "google_cloud_run_v2_service_iam_member" "public_api_transport" {
  count = var.deploy_runtime ? 1 : 0

  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.api[0].location
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "migration" {
  count = var.deploy_runtime ? 1 : 0

  name                = "tradearena-migrate-staging"
  location            = var.gcp_region
  deletion_protection = false
  labels              = local.labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.migration.email
      max_retries     = 0
      timeout         = "900s"

      containers {
        image   = var.api_image
        command = ["python", "-m", "tradearena", "migrate"]

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime["database_url"].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.migration_database,
  ]


  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}

resource "google_project_iam_custom_role" "staging_deployer" {
  role_id     = "tradeArenaStagingDeployer"
  title       = "TradeArena staging deployer"
  description = "Actualiza y ejecuta únicamente los artefactos Cloud Run de staging."
  stage       = "GA"
  permissions = [
    "run.executions.get",
    "run.jobs.get",
    "run.jobs.run",
    "run.jobs.update",
    "run.operations.get",
    "run.services.get",
    "run.services.update",
  ]
}

resource "google_project_iam_member" "deployer_run" {
  project = var.gcp_project_id
  role    = google_project_iam_custom_role.staging_deployer.name
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_writer" {
  project    = var.gcp_project_id
  location   = google_artifact_registry_repository.backend.location
  repository = google_artifact_registry_repository.backend.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_uses_api" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_uses_migration" {
  service_account_id = google_service_account.migration.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "tradearena-github"
  display_name              = "TradeArena GitHub Actions"
  description               = "OIDC sin claves persistentes para staging"

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub main staging"
  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.ref"              = "assertion.ref"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# TA-039 habilita Scheduler y crea su identidad, pero no define targets. Los
# jobs financieros y su IAM quedan expresamente reservados para la Fase 4.
resource "google_project_iam_member" "scheduler_service_agent" {
  project = var.gcp_project_id
  role    = "roles/cloudscheduler.serviceAgent"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"

  depends_on = [google_project_service.required]
}

data "google_project" "current" {
  project_id = var.gcp_project_id
}

resource "neon_project" "staging" {
  name                      = var.neon_project_name
  region_id                 = "aws-eu-central-1"
  history_retention_seconds = 86400
  store_password            = "yes"

  default_endpoint_settings {
    autoscaling_limit_min_cu = 0.25
    autoscaling_limit_max_cu = 1
    suspend_timeout_seconds  = 300
  }
}

resource "vercel_project" "web" {
  name                         = var.vercel_project_name
  framework                    = "nextjs"
  root_directory               = "web"
  install_command              = "corepack enable && pnpm install --frozen-lockfile"
  build_command                = "pnpm generate:api && pnpm build"
  node_version                 = "24.x"
  auto_assign_custom_domains   = false
  git_fork_protection          = true
  preview_deployments_disabled = false

  git_repository = {
    type              = "github"
    repo              = var.github_repository
    production_branch = "production-closed"
  }
}

resource "vercel_custom_environment" "staging" {
  project_id  = vercel_project.web.id
  name        = "staging"
  description = "Entorno integrado no productivo desplegado solo tras main"
}

locals {
  vercel_non_secret_environment = {
    AUTH0_DOMAIN    = var.auth0_domain
    AUTH0_CLIENT_ID = var.auth0_client_id
    APP_BASE_URL    = var.vercel_staging_base_url
  }
}

resource "vercel_project_environment_variable" "staging_non_secret" {
  for_each = local.vercel_non_secret_environment

  project_id             = vercel_project.web.id
  key                    = each.key
  value                  = each.value
  sensitive              = false
  custom_environment_ids = [vercel_custom_environment.staging.id]
  comment                = "Gestionada por Terraform para staging"
}

resource "vercel_project_environment_variable" "staging_api_url" {
  count = var.deploy_runtime ? 1 : 0

  project_id             = vercel_project.web.id
  key                    = "API_BASE_URL"
  value                  = google_cloud_run_v2_service.api[0].uri
  sensitive              = false
  custom_environment_ids = [vercel_custom_environment.staging.id]
  comment                = "Gestionada por Terraform para staging"
}
