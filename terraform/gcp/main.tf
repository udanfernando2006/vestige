terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# 1. VPC Network
resource "google_compute_network" "vestige_vpc" {
  name                    = "vestige-vpc"
  auto_create_subnetworks = "true"
}

# 2. Firewall Rules (Open SSH & Vestige API Port)
resource "google_compute_firewall" "vestige_firewall" {
  name    = "vestige-allow-ssh-http"
  network = google_compute_network.vestige_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22", "8080"] 
  }

  source_ranges = ["0.0.0.0/0"]
}

# 3. Static Public IP
resource "google_compute_address" "vestige_static_ip" {
  name = "vestige-static-ip"
}

# 4. Compute Engine VM
resource "google_compute_instance" "vestige_vm" {
  name         = "vestige-backend-vm"
  machine_type = "n2-standard-2"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30 # Max free-tier limit
      type  = "pd-standard"
    }
  }

  network_interface {
    network = google_compute_network.vestige_vpc.name
    access_config {
      nat_ip = google_compute_address.vestige_static_ip.address
    }
  }

  # SSH Key Injection and Cloud-Init
  metadata = {
    ssh-keys = "${var.ssh_user}:${file(pathexpand(var.ssh_pub_key_path))}"
    
    # Notice the explicit shebang below. Missing this causes the cloud-init to silently skip execution, which previously caused issues during the Azure deployment.
    user-data = <<-EOF
      #!/bin/bash
      
      # Setup 2GB Swap Space
      fallocate -l 2G /swapfile
      chmod 600 /swapfile
      mkswap /swapfile
      swapon /swapfile
      echo '/swapfile none swap sw 0 0' >> /etc/fstab

      # Install Docker Engine
      apt-get update
      apt-get install -y ca-certificates curl gnupg lsb-release
      mkdir -p /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
      apt-get update
      apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

      # Prepare Vestige Workspace
      mkdir -p /home/${var.ssh_user}/vestige/logs
      chown -R ${var.ssh_user}:${var.ssh_user} /home/${var.ssh_user}/vestige
    EOF
  }

  tags = ["vestige-node"]
}