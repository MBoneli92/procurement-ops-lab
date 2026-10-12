data "cloudfoundry_org" "this" {
  name = var.cf_org_name
}

resource "cloudfoundry_space" "customer" {
  name = var.customer
  org  = data.cloudfoundry_org.this.id
}

resource "cloudfoundry_space_role" "developer" {
  username = var.admin_user
  type     = "space_developer"
  space    = cloudfoundry_space.customer.id
}

resource "cloudfoundry_space_role" "manager" {
  username = var.admin_user
  type     = "space_manager"
  space    = cloudfoundry_space.customer.id
}

data "cloudfoundry_service_plan" "xsuaa_application" {
  name                  = "application"
  service_offering_name = "xsuaa"
}

locals {
  xsappname = "procurement-${var.customer}"
}

resource "cloudfoundry_service_instance" "xsuaa" {
  name         = "xsuaa-${var.customer}"
  type         = "managed"
  space        = cloudfoundry_space.customer.id
  service_plan = data.cloudfoundry_service_plan.xsuaa_application.id
  parameters = jsonencode({
    xsappname     = local.xsappname
    "tenant-mode" = "dedicated"
    scopes        = [{ name = "$XSAPPNAME.Viewer", description = "Read procurement data" }]
    "role-templates" = [{
      name               = "Viewer"
      description        = "Read only"
      "scope-references" = ["$XSAPPNAME.Viewer"]
    }]
  })
    depends_on = [cloudfoundry_space_role.developer]
}

resource "btp_subaccount_role_collection" "viewer" {
  subaccount_id = var.subaccount_id
  name          = "${var.customer} Viewer"
  description   = "Read access for customer ${var.customer}"
  roles = [{
    name                 = "Viewer"
    role_template_app_id = "${local.xsappname}${var.xsuaa_app_suffix}"
    role_template_name   = "Viewer"
  }]
  depends_on = [cloudfoundry_service_instance.xsuaa]
}

resource "btp_subaccount_role_collection_assignment" "viewer_user" {
  subaccount_id        = var.subaccount_id
  role_collection_name = btp_subaccount_role_collection.viewer.name
  user_name            = var.admin_user
}