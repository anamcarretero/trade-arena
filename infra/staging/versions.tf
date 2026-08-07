terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  backend "gcs" {}

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.39"
    }
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.14"
    }
    vercel = {
      source  = "vercel/vercel"
      version = "~> 5.4"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "neon" {}

provider "vercel" {
  team = var.vercel_team
}
