# 1. Fetch the latest official Ubuntu 24.04 Amazon Machine Image (AMI)
data "aws_ami" "ubuntu" {
  most_recent = true
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  owners = ["099720109477"] # Canonical
}

# 2. Create a default VPC network wrapper
resource "aws_default_vpc" "default" {}

# 3. Create a Security Group (Firewall)
resource "aws_security_group" "vestige_sg" {
  name        = "vestige-backend-sg"
  description = "Allow inbound traffic for Vestige API and SSH"
  vpc_id      = aws_default_vpc.default.id

  # SSH Access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Spring Boot API Access
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound rule allowing containers to fetch updates/pull public images
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 4. Provision the EC2 Instance
resource "aws_instance" "vestige_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  root_block_device {
    volume_size = 25  # Expands the drive to 25GB (Free tier covers up to 30GB)
    volume_type = "gp3"
  }

  vpc_security_group_ids = [aws_security_group.vestige_sg.id]

# Cloud-init shell script to install Docker, add Swap, and prepare the workspace
  user_data = <<-EOF
              #!/bin/bash
              
              # 1. Create a 2GB Swap file to prevent Out-Of-Memory crashes on 1GB instances
              sudo dd if=/dev/zero of=/swapfile bs=128M count=16
              sudo chmod 600 /swapfile
              sudo mkswap /swapfile
              sudo swapon /swapfile
              echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
              
              # 2. Install Docker
              sudo apt-get update
              sudo apt-get install -y docker.io docker-compose
              sudo systemctl start docker
              sudo systemctl enable docker

              # 3. Set up application workspace
              mkdir -p /home/ubuntu/vestige
              sudo chown -R ubuntu:ubuntu /home/ubuntu/vestige
              EOF

  tags = {
    Name = "Vestige-Cloud-Backend"
  }
}