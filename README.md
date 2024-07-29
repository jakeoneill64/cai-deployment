# Deployment config of web app using terraform, kubernetes, python and bash.

__Steps to deploy:__

1. Install terraform & Git https://developer.hashicorp.com/terraform/install https://git-scm.com/downloads
2. `git clone https://github.com/jakeoneill64/cai-devops-task.git`
3. navigate to `./terraform`
4. `terraform init`
5. fill in the variables for deployment in `terraform.tfvars`
6. `terraform apply`

_the result should look something like_

```Apply complete! Resources: 2 added, 0 changed, 0 destroyed.

Outputs:

web-service-url = "http://ec2aeicneeru.eu-west-2.compute.amazonaws.com"
```

You can use this url to access the exposed web service.

__NB the deployment takes longer than the terraform application steps, so the endpoint will not be immediately available.__