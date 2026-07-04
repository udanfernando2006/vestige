terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# 1. Resource Group (The container for all Vestige resources)
resource "azurerm_resource_group" "vestige_rg" {
  name     = "vestige-resources"
  location = "southeastasia"
}

# 2. Virtual Network (Equivalent to AWS VPC)
resource "azurerm_virtual_network" "vestige_vnet" {
  name                = "vestige-network"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.vestige_rg.location
  resource_group_name = azurerm_resource_group.vestige_rg.name
}

# 3. Subnet
resource "azurerm_subnet" "vestige_subnet" {
  name                 = "internal"
  resource_group_name  = azurerm_resource_group.vestige_rg.name
  virtual_network_name = azurerm_virtual_network.vestige_vnet.name
  address_prefixes     = ["10.0.2.0/24"]
}

# 4. Public IP Address (Equivalent to AWS Elastic IP)
resource "azurerm_public_ip" "vestige_public_ip" {
  name                = "vestige-pip"
  resource_group_name = azurerm_resource_group.vestige_rg.name
  location            = azurerm_resource_group.vestige_rg.location
  allocation_method   = "Static"
  sku                 = "Standard"
}

# 5. Network Security Group (Equivalent to AWS Security Group)
resource "azurerm_network_security_group" "vestige_nsg" {
  name                = "vestige-nsg"
  location            = azurerm_resource_group.vestige_rg.location
  resource_group_name = azurerm_resource_group.vestige_rg.name

  # Rule for SSH (Port 22)
  security_rule {
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Rule for Vestige Spring Boot API / Frontend (Port 8080)
  security_rule {
    name                       = "VestigeAPI"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8080"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# 6. Network Interface Card (NIC)
resource "azurerm_network_interface" "vestige_nic" {
  name                = "vestige-nic"
  location            = azurerm_resource_group.vestige_rg.location
  resource_group_name = azurerm_resource_group.vestige_rg.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.vestige_subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vestige_public_ip.id
  }
}

# Connect the Security Group to the Network Interface
resource "azurerm_network_interface_security_group_association" "nsg_assoc" {
  network_interface_id      = azurerm_network_interface.vestige_nic.id
  network_security_group_id = azurerm_network_security_group.vestige_nsg.id
}

# 7. Linux Virtual Machine (Equivalent to AWS EC2 t3.micro)
resource "azurerm_linux_virtual_machine" "vestige_vm" {
  name                = "vestige-backend-vm"
  resource_group_name = azurerm_resource_group.vestige_rg.name
  location            = azurerm_resource_group.vestige_rg.location
  size                = "Standard_D2s_v5"
  admin_username      = "azureuser"
  network_interface_ids = [
    azurerm_network_interface.vestige_nic.id,
  ]

  admin_ssh_key {
    username   = "azureuser"
    public_key = file("${path.module}/vestige-azure-key.pub")
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 30
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(<<-EOF
    #!/bin/bash
    # 1. Setup 2GB Swap Space
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

    # 2. Install Docker and Docker Compose v2
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose-v2
    sudo systemctl enable --now docker

    # 3. Create the workspace and grant permissions to the azureuser
    mkdir -p /home/azureuser/vestige
    chown -R azureuser:azureuser /home/azureuser/vestige
  EOF
  )
}

# Output the Public IP so you can easily copy it
output "backend_public_ip" {
  value       = azurerm_public_ip.vestige_public_ip.ip_address
  description = "The public IP address of the Vestige Azure VM"
}