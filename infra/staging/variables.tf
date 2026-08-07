variable "gcp_project_id" {
  description = "Proyecto GCP dedicado a staging."
  type        = string
}

variable "gcp_region" {
  description = "Región de Cloud Run, Artifact Registry y Scheduler."
  type        = string
  default     = "europe-west3"

  validation {
    condition     = var.gcp_region == "europe-west3"
    error_message = "TA-039 fija staging en europe-west3."
  }
}

variable "github_repository" {
  description = "Repositorio autorizado para OIDC, en formato owner/name."
  type        = string
  default     = "anamcarretero/trade-arena"
}

variable "api_image" {
  description = "Digest OCI ya publicado que inicializa servicio y job de migración."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = !var.deploy_runtime || (
      var.api_image != null && can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
    )
    error_message = "Con deploy_runtime=true, api_image debe ser un digest OCI sha256."
  }
}

variable "deploy_runtime" {
  description = "Crea API/job solo después de publicar imagen y cargar versiones de secretos."
  type        = bool
  default     = false
}

variable "auth0_domain" {
  description = "Dominio público del tenant Auth0 europeo, sin protocolo."
  type        = string
}

variable "auth0_client_id" {
  description = "Client ID público compartido por API y BFF."
  type        = string
}

variable "neon_project_name" {
  description = "Nombre del proyecto Neon de staging."
  type        = string
  default     = "tradearena-staging"
}

variable "vercel_team" {
  description = "Slug o ID del equipo Vercel; vacío para cuenta personal."
  type        = string
  default     = null
  nullable    = true
}

variable "vercel_project_name" {
  description = "Nombre del proyecto Vercel de la PWA/BFF."
  type        = string
  default     = "tradearena-staging"
}

variable "vercel_staging_base_url" {
  description = "Origen HTTPS estable ya autorizado para staging; Terraform no crea dominios."
  type        = string

  validation {
    condition     = startswith(var.vercel_staging_base_url, "https://")
    error_message = "El origen estable de staging debe usar HTTPS."
  }
}

variable "cloud_run_deletion_protection" {
  description = "Protege el servicio durante la operación normal; desactivar solo en retirada confirmada."
  type        = bool
  default     = true
}
