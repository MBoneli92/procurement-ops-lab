terraform {
  required_version = ">= 1.6"
  required_providers {
    btp = {
      source  = "SAP/btp"
      version = "~> 1.0"
    }
    cloudfoundry = {
      source  = "cloudfoundry/cloudfoundry"
      version = "~> 1.0"
    }
  }
}

provider "btp" {
  globalaccount = var.globalaccount
}

provider "cloudfoundry" {
  api_url = var.cf_api_url
}