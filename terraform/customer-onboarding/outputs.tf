output "space_name" {
  value = cloudfoundry_space.customer.name
}

output "role_collection" {
  value = btp_subaccount_role_collection.viewer.name
}