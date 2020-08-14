from kubernetes import client, config
from .exec_client import stream

from pinta.api.schemas.job import SymmetricJob, PSWorkerJob, MPIJob, ImageBuilderJob
from pinta.api.core.config import settings


def get_vcjob(id: int):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CustomObjectsApi()
    api_response = api.get_namespaced_custom_object(
        group="batch.volcano.sh",
        version="v1alpha1",
        namespace="default",
        plural="jobs",
        name="pinta-job-" + str(id)
    )
    return api_response


def create_symmetric_pintajob(job_in: SymmetricJob, id: int):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CustomObjectsApi()
    replica = {
        "spec": {
            "containers": [{
                "name": "pinta-image",
                "image": job_in.image,
                "workingDir": job_in.working_dir,
                "command": ["sh", "-c", job_in.command],
                "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
            }],
            "restartPolicy": "OnFailure"
        }
    }
    ptjob = {
        "apiVersion": "pinta.qed.usc.edu/v1",
        "kind": "PintaJob",
        "metadata": {
            "name": "pinta-job-" + str(id)
        },
        "spec": {
            "type": "symmetric",
            "volumes": job_in.volumes,
            "replica": replica,
            "numReplicas": job_in.num_replicas
        }
    }
    api_response = api.create_namespaced_custom_object(
        group="pinta.qed.usc.edu",
        version="v1",
        namespace="default",
        plural="pintajobs",
        body=ptjob
    )
    return api_response


def create_ps_worker_pintajob(job_in: PSWorkerJob, id: int):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CustomObjectsApi()
    master = {
        "spec": {
            "containers": [{
                "name": "ps",
                "image": job_in.image,
                "workingDir": job_in.working_dir,
                "command": ["sh", "-c", job_in.ps_command],
                "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
            }],
            "restartPolicy": "OnFailure"
        }
    }
    replica = {
        "spec": {
            "containers": [{
                "name": "worker",
                "image": job_in.image,
                "workingDir": job_in.working_dir,
                "command": ["sh", "-c", job_in.worker_command],
                "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
            }],
            "restartPolicy": "OnFailure"
        }
    }
    ptjob = {
        "apiVersion": "pinta.qed.usc.edu/v1",
        "kind": "PintaJob",
        "metadata": {
            "name": "pinta-job-" + str(id)
        },
        "spec": {
            "type": "ps-worker",
            "volumes": job_in.volumes,
            "master": master,
            "replica": replica,
            "numMasters": job_in.num_ps,
            "numReplicas": job_in.num_workers
        }
    }
    api_response = api.create_namespaced_custom_object(
        group="pinta.qed.usc.edu",
        version="v1",
        namespace="default",
        plural="pintajobs",
        body=ptjob
    )
    return api_response


def create_mpi_pintajob(job_in: MPIJob, id: int):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CustomObjectsApi()
    master = {
        "spec": {
            "containers": [{
                "name": "master",
                "image": job_in.image,
                "workingDir": job_in.working_dir,
                "command": ["sh", "-c", job_in.master_command],
                "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
            }],
            "restartPolicy": "OnFailure"
        }
    }
    replica = {
        "spec": {
            "containers": [{
                "name": "replica",
                "image": job_in.image,
                "workingDir": job_in.working_dir,
                "command": ["sh", "-c", job_in.replica_command],
                "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
            }],
            "restartPolicy": "OnFailure"
        }
    }
    ptjob = {
        "apiVersion": "pinta.qed.usc.edu/v1",
        "kind": "PintaJob",
        "metadata": {
            "name": "pinta-job-" + str(id)
        },
        "spec": {
            "type": "mpi",
            "volumes": job_in.volumes,
            "master": master,
            "replica": replica,
            "numMasters": 1,
            "numReplicas": job_in.num_replicas
        }
    }
    api_response = api.create_namespaced_custom_object(
        group="pinta.qed.usc.edu",
        version="v1",
        namespace="default",
        plural="pintajobs",
        body=ptjob
    )
    return api_response


def create_image_builder_pintajob(job_in: ImageBuilderJob, id: int):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CustomObjectsApi()
    replica = {
        "spec": {
            "containers": [
                {
                    "name": "dockerd",
                    "image": "docker:stable-dind",
                    "securityContext": {"privileged": True},
                    "command": ["dockerd", "--host=tcp://0.0.0.0:2375"],
                    "volumeMounts": [{
                        "name": "config-volume",
                        "mountPath": "/etc/docker/daemon.json",
                        "subPath": "daemon.json"
                    }]
                },
                {
                    "name": "docker-cli",
                    "image": "docker:stable",
                    "env": [{"name": "DOCKER_HOST", "value": "tcp://127.0.0.1:2375"}],
                    "command": [
                        "sh", "-c",
                        "docker info >/dev/null 2>&1; "
                        "while [ $? -ne 0 ] ; do sleep 3; docker info >/dev/null 2>&1; done; "
                        f"docker create -it --name=image-builder-container {job_in.from_image} sh; "
                        f"docker start image-builder-container; "
                        "while true; do sleep 86400; done"
                    ]
                }
            ],
            "volumes": [
                {
                    "name": "config-volume",
                    "configMap": {
                        "name": "docker-insecure-registries"
                    }
                }
            ]
        }
    }
    ptjob = {
        "apiVersion": "pinta.qed.usc.edu/v1",
        "kind": "PintaJob",
        "metadata": {
            "name": "pinta-job-" + str(id)
        },
        "spec": {
            "type": "image-builder",
            "volumes": job_in.volumes,
            "replica": replica,
            "numReplicas": 1
        }
    }
    api_response = api.create_namespaced_custom_object(
        group="pinta.qed.usc.edu",
        version="v1",
        namespace="default",
        plural="pintajobs",
        body=ptjob
    )
    return api_response


def commit_image_builder(name: str, id: int, username: str):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CoreV1Api()
    exec_command = [
        "/bin/sh",
        "-c",
        f"docker commit image-builder-container {settings.REGISTRY_SERVER}/{username}/{name}; "
        f"docker push {settings.REGISTRY_SERVER}/{username}/{name}"
    ]
    resp = stream(
        func=api.connect_get_namespaced_pod_exec,
        name=f"pinta-job-{id}-image-builder-0",
        namespace="default",
        command=exec_command,
        container="docker-cli",
        stderr=True, stdin=False,
        stdout=True, tty=False
    )
    print("Response: " + resp)
    api = client.CustomObjectsApi()
    api_response = api.delete_namespaced_custom_object(
        group="pinta.qed.usc.edu",
        version="v1",
        namespace="default",
        plural="pintajobs",
        name="pinta-job-" + str(id)
    )
    return api_response


def delete_vcjob(id: int):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CustomObjectsApi()
    api_response = api.delete_namespaced_custom_object(
        group="pinta.qed.usc.edu",
        version="v1",
        namespace="default",
        plural="pintajobs",
        name="pinta-job-" + str(id)
    )
    return api_response

