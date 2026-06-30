variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "The target AWS region for deployment"
}

variable "instance_type" {
  type        = string
  default     = "t3.micro" 
  description = "EC2 instance size for the Vestige backend"
}

variable "key_name" {
  type        = string
  default     = "vestige-key"
  description = "The name of your AWS SSH Key Pair"
}