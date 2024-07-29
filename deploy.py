from kubernetes import client, config
import sys
import docker
import os
import logging
import yaml

_cai_object_names = {
    'web-service', 'api-service', 'devops-test-api', 'devops-test-web',
    'mysql-pv-claim', 'mysql-pv','mysql-service', 'redis-service', 'redis',
    'mysql', 'cai-ingress', 'cai-secrets'
}

def clean(
    app_client, core_client, networking_client
):

    deployment_names = [item.metadata.name for item in app_client.list_namespaced_deployment(namespace='default').items]
    services_names = [item.metadata.name for item in core_client.list_namespaced_service(namespace='default').items]
    persistent_volume_names = [item.metadata.name for item in core_client.list_persistent_volume().items]
    persistent_volume_claims = [item.metadata.name for item in core_client.list_namespaced_persistent_volume_claim(namespace='default').items]
    ingress_names = [item.metadata.name for item in networking_client.list_namespaced_ingress(namespace='default').items]
    secret_names = [item.metadata.name for item in core_client.list_namespaced_secret(namespace='default').items]

    errors = []

    # don't stop things that don't belong to us.
    for deployment in _cai_object_names.intersection(deployment_names):
        try:
            app_client.delete_namespaced_deployment(deployment, 'default')
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

    for ingress in _cai_object_names.intersection(ingress_names):
        try:
            networking_client.delete_namespaced_ingress(ingress, 'default')
        except Exception as e:
            errors.append(str(e))

    if len(errors) > 0:
        logger.warning("tore down cai deployment with errors " + ','.join(errors))
    else:
        logger.info("successfully tore down cai deployment")

def process_resource_file(
    app_client, core_client, networking_client, resource_file
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
                    case 'ingress':
                        networking_client.create_namespaced_ingress(namespace='default', body=definition)
                    case 'secret':
                        core_client.create_namespaced_secret(namespace='default', body=definition)
            except Exception as e:
                logger.error(f'could not create object from definition {str(e)}')


def deploy(
    app_client, core_client, networking_client
):
    docker_client = docker.from_env()

    for image_name, filename in \
        [(filename[len('Dockerfile.'):], filename) for filename in os.listdir('.') if filename.startswith('Dockerfile.')]:
        logger.info('building docker image: ' + image_name)
        try:
            docker_client.images.build(path='.', dockerfile=filename, tag=image_name)
        except Exception as e:
            logger.fatal(f'docker image build for {image_name} failed: {str(e)}')
            return
        logger.info(f'successfully built {image_name}')

    process_resource_file(app_client, core_client, networking_client, './secret.yaml')
    process_resource_file(app_client, core_client, networking_client, './deployment.yaml')
    process_resource_file(app_client, core_client, networking_client, './service.yaml')




if __name__ == '__main__':

    config.load_kube_config()

    app_client = client.AppsV1Api()
    core_client = client.CoreV1Api()
    networking_client = client.NetworkingV1Api()

    logger = logging.getLogger()
    file_handler = logging.FileHandler('log/cai-task.log')
    console_handler = logging.StreamHandler()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    args = set(map(lambda arg: arg.lower(), sys.argv[1:]))

    if 'clean' in args:
        clean(app_client, core_client, networking_client)

    if 'deploy' in args:
        deploy(app_client, core_client, networking_client)