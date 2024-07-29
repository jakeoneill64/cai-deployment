provider "aws" {
  region = "eu-west-2"
}

resource "aws_instance" "cai-devops-instance" {
  ami           = "ami-07c1b39b7b3d2525d"
  instance_type = "t2.medium"
  key_name       = var.key_name

  security_groups = [aws_security_group.cai-devops-sg.name]
  user_data = file("../env-setup.sh")

  root_block_device {
    volume_size = 50
  }

  tags = {
    lifecycle: "transient"
  }
}

resource "aws_security_group" "cai-devops-sg" {
  name        = "cai-devops-sg"
  description = "Allow inbound traffic on port 80 and 22 from approved cidr block"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.ingress_cidr]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ingress_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    lifecycle: "transient"
  }
}

