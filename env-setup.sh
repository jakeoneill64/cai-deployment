#!/bin/bash



# set up repo
sudo apt-get update
git clone https://github.com/jakeoneill64/cai-devops-task.git
sudo mv cai-devops-task /opt/
sudo chown -R ubuntu /opt/cai-devops-task
mkdir /opt/cai-devops-task/log
exec > >(tee -a /opt/cai-devops-task/log/deployment.log) 2>&1 # redirect stdin & stderr to log files

echo WHO AM I
whoami

# https://docs.docker.com/engine/install/ubuntu/
echo "installing docker"
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

whoami
echo "adding ubuntu to the docker group"
sudo usermod -aG docker ubuntu && sudo -i -u ubuntu bash<<EOF
# https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/
echo "installing kubectl"
curl -LO https://dl.k8s.io/release/v1.30.0/bin/linux/amd64/kubectl
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# https://minikube.sigs.k8s.io/docs/start/?arch=%2Flinux%2Fx86-64%2Fstable%2Fbinary+download
echo "installing minikube"
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
minikube start

# important step, the env-vars need to propagate down, this is a work around
minikube docker-env > .minikube_vars.sh
source .minikube_vars.sh

cd /opt/cai-devops-task
sudo apt install -y python3.12-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 kubes.py clean deploy forward
EOF
