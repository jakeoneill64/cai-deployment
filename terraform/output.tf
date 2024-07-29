output "web-service-url" {
  value = "http://${aws_instance.cai-devops-instance.public_dns}"
  description = "The url of the deployed webservice"
}