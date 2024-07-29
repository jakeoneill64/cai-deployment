import time
from git import Repo
from kubernetes import client, config
import sys
import docker
import os
import logging
import yaml
import string
import secrets
import base64

_cai_object_names = {
    'web-service', 'api-service', 'devops-test-api', 'devops-test-web',
    'mysql-pv-claim', 'mysql-pv','mysql-service', 'redis-service', 'redis',
    'mysql', 'cai-ingress', 'cai-secrets'
}

def cleanup_submodules(repo: Repo):
    repo.git.clean('-df')
    repo.git.reset('HEAD', '--hard')

def clean(app_client, core_client):

    git_repo = Repo('.')
    git_repo.submodule_update(init=True, recursive=True)
    api_repo = Repo('./devops-test-api')
    web_repo = Repo('./devops-test-web')
    cleanup_submodules(api_repo)
    cleanup_submodules(web_repo)

    deployment_names = [item.metadata.name for item in app_client.list_namespaced_deployment(namespace='default').items]
    services_names = [item.metadata.name for item in core_client.list_namespaced_service(namespace='default').items]
    persistent_volume_names = [item.metadata.name for item in core_client.list_persistent_volume().items]
    persistent_volume_claims = [item.metadata.name for item in core_client.list_namespaced_persistent_volume_claim(namespace='default').items]
    secret_names = [item.metadata.name for item in core_client.list_namespaced_secret(namespace='default').items]

    errors = []

    # don't stop things that don't belong to us.
    for deployment in _cai_object_names.intersection(deployment_names):
        try:
            app_client.delete_namespaced_deployment(deployment, 'default')
        except Exception as e:
            errors.append(str(e))

    try:
        core_client.delete_namespace('cai', 'default')
    except Exception as e:
        errors.append(str(e))

    for service in _cai_object_names.intersection(services_names):
        try:
            core_client.delete_namespaced_service(service, 'default')
        except Exception as e:
            errors.append(str(e))

    for pv in _cai_object_names.intersection(persistent_volume_names):
        try:
            core_client.delete_persistent_volume(pv)
        except Exception as e:
            errors.append(str(e))

    for pvc in _cai_object_names.intersection(persistent_volume_claims):
        try:
            core_client.delete_namespaced_persistent_volume_claim(pvc, 'default')
        except Exception as e:
            errors.append(str(e))

    for secret in _cai_object_names.intersection(secret_names):
        try:
            core_client.delete_namespaced_secret(secret, 'default')
        except Exception as e:
            errors.append(str(e))

    if len(errors) > 0:
        logger.warning("tore down cai deployment with errors " + ','.join(errors))
    else:
        logger.info("successfully tore down cai deployment")

def _pod_ready(pod):
        for condition in pod.status.conditions:
            if condition.type == 'Ready' and condition.status == 'True':
                return True

def _process_resource_file(
    app_client, core_client, resource_file
):
    with open(resource_file, 'r') as file:
        resource_definitions = yaml.safe_load_all(file)
        for definition in resource_definitions:
            try:
                match definition['kind'].lower():
                    case 'deployment':
                        app_client.create_namespaced_deployment(namespace='default', body=definition)
                    case 'service':
                        core_client.create_namespaced_service(namespace='default', body=definition)
                    case 'persistentvolume':
                        core_client.create_persistent_volume(body=definition)
                    case 'persistentvolumeclaim':
                        core_client.create_namespaced_persistent_volume_claim(namespace='default', body=definition)
                    case 'secret':
                        core_client.create_namespaced_secret(namespace='default', body=definition)
            except Exception as e:
                logger.error(f'could not create object from definition {str(e)}')

def _update_env_values(file_path, replacements):

    with open(file_path, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    kv_dict = dict(replacement.split('=', 1) for replacement in replacements)


    with open(file_path, 'w') as file:
        file.writelines(updated_lines)

def deploy(
    app_client, core_client
):


    password_chars = string.ascii_letters + string.digits + string.punctuation
    db_root_password = ''.join(secrets.choice(password_chars) for i in range(20))

    secret_yaml_contents = \
    f""" 
    apiVersion: v1
        kind: Secret
        metadata:
            name: cai-secrets
        type: Opaque
        data:
            root-password: {base64.b64encode(db_root_password.encode('utf-8'))}
    """

    with open('./secret.yaml', 'w') as secretFile:
        secretFile.write(secret_yaml_contents)

    _update_env_values(
        './devops-test-api/.env',
        {
            'DB_HOST': 'mysql.cai',
            'REDIS_HOST': 'redis.cai',
            'DB_PASSWORD': db_root_password
        }
    )

    _update_env_values(
        './devops-test-web/.env',
        {
            'DB_HOST': 'mysql.cai',
            'DB_PASSWORD': db_root_password
        }
    )

    docker_client = docker.from_env()

    for image_name, filename in \
        [(filename[len('Dockerfile.'):], filename) for filename in os.listdir('.') if filename.startswith('Dockerfile.')]:
        logger.info('building docker image: ' + image_name)
        try:
            image, logs = docker_client.images.build(path='.', dockerfile=filename, tag=image_name)
        except Exception as e:
            logger.fatal(f'docker image build for {image_name} failed: {str(e)}')
            return
        logger.info(f'successfully built {image_name}')

    core_client.create_namespace('cai')
    _process_resource_file(app_client, core_client, './secret.yaml')
    _process_resource_file(app_client, core_client, './persistence.yaml')
    _process_resource_file(app_client, core_client, './deployment.yaml')

    mysql_pod_name = [
                item.metadata.name for item in core_client.list_namespaced_pod('default', label_selector='app=mysql').items
    ][0]

    wait_time = 2
    while not _pod_ready(core_client.read_namespaced_pod(mysql_pod_name, 'default')):
        if wait_time > 256:
            logger.error('mysql took too long to initialise, exiting')

        # would be better to use asycio for more complex setups.
        time.sleep(wait_time)
        wait_time *= 2

    _process_resource_file(app_client, core_client, './api-deployment.yaml')
    _process_resource_file(app_client, core_client, './service.yaml')


if __name__ == '__main__':

    config.load_kube_config()

    app_client = client.AppsV1Api()
    core_client = client.CoreV1Api()

    logger = logging.getLogger()
    logger.setLevel('DEBUG')
    file_handler = logging.FileHandler('log/cai-task.log')
    console_handler = logging.StreamHandler()
    console_handler.setLevel('DEBUG')
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    args = set(map(lambda arg: arg.lower(), sys.argv[1:]))

    if 'clean' in args:
        clean(app_client, core_client)

    if 'deploy' in args:
        deploy(app_client, core_client)