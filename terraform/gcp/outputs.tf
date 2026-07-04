output "backend_public_ip" {
  description = "Public IP address of the Vestige GCP VM"
  value       = google_compute_address.vestige_static_ip.address
}