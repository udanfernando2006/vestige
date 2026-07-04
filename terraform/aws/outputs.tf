output "backend_public_ip" {
  value       = aws_instance.vestige_server.public_ip
  description = "The public IP address of the remote cloud backend"
}