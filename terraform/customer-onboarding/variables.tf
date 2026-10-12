variable "globalaccount" {
  description = "Global account subdomain"
  type        = string
  default     = "27485d6atrial-ga"
}

variable "subaccount_id" {
  description = "Subaccount where customers are onboarded"
  type        = string
}

variable "cf_api_url" {
  type    = string
  default = "https://api.cf.us10-001.hana.ondemand.com"
}

variable "cf_org_name" {
  type    = string
  default = "27485d6atrial"
}

variable "xsuaa_app_suffix" {
  description = "Suffix the XSUAA adds to every xsappname in this subaccount, e.g. !t723779"
  type        = string
}

variable "customer" {
  description = "Customer name, lowercase letters, digits and hyphens"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.customer))
    error_message = "Use 3 to 31 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "admin_user" {
  description = "User who gets access to the customer space and role collection"
  type        = string
}