from kubernetes import client, config
from kubernetes.stream import stream

from pinta.api.schemas.job import JobType
from pinta.api.core.config import settings
from pinta.api.models import Job


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


def create_pintajob(job_in: Job, volumes):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CustomObjectsApi()

    spec = {
        "type": job_in.type,
        "volumes": volumes
    }
    if JobType.master_role(job_in.type):
        spec["master"] = {
            "spec": {
                "containers": [{
                    "name": JobType.master_role(job_in.type),
                    "image": job_in.image,
                    "workingDir": job_in.working_dir,
                    "command": ["sh", "-c", job_in.master_command],
                    "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
                }],
                "restartPolicy": "OnFailure"
            }
        }
    if job_in.type == JobType.image_builder:
        spec["replica"] = {
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
                            f"docker create -it --name=image-builder-container {job_in.image} sh; "
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
    else:
        spec["replica"] = {
            "spec": {
                "containers": [{
                    "name": JobType.replica_role(job_in.type),
                    "image": job_in.image,
                    "workingDir": job_in.working_dir,
                    "command": ["sh", "-c", job_in.replica_command],
                    "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
                }],
                "restartPolicy": "OnFailure"
            }
        }
    if job_in.num_masters:
        spec["numMasters"] = job_in.num_masters
    if job_in.num_replicas:
        spec["numReplicas"] = job_in.num_replicas

    ptjob = {
        "apiVersion": "pinta.qed.usc.edu/v1",
        "kind": "PintaJob",
        "metadata": {
            "name": f"pinta-job-{job_in.id}"
        },
        "spec": spec
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


def delete_pintajob(id: int):
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


def get_pintajob_log(id: int, role: str, num: int):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CoreV1Api()
    api_response = api.read_namespaced_pod_log(f"pinta-job-{id}-{role}-{num}", "default")
    return api_response
