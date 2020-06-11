from kubernetes import client, config
from .exec_client import stream
from typing import Optional, List

from pinta.api.schemas.job import SymmetricJob, ImageBuilderJob
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

import websockets
import asyncio


def get_vcjob(id: int):
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


def create_vcjob(job_in: SymmetricJob, id: int):
    config.load_incluster_config()
    api = client.CustomObjectsApi()
    tasks = [{
        "replicas": job_in.min_num_replicas,
        "name": "replica",
        "template": {
            "spec": {
                "containers": [{
                    "name": "pinta-image",
                    "image": job_in.image,
                    "workingDir": job_in.working_dir,
                    "command": ["sh", "-c", job_in.command],
                    "ports": [{"containerPort": 2222, "name": "pinta-job-port"}]
                }]
            }
        }
    }]
    vcjob = {
        "apiVersion": "batch.volcano.sh/v1alpha1",
        "kind": "Job",
        "metadata": {
            "name": "pinta-job-" + str(id)
        },
        "spec": {
            "minAvailable": job_in.min_num_replicas,
            "schedulerName": "volcano",
            "plugins": {"env": [], "svc": []},
            "policies": [{"event": "PodEvicted", "action": "RestartJob"}],
            "tasks": tasks
        }
    }
    api_response = api.create_namespaced_custom_object(
        group="batch.volcano.sh",
        version="v1alpha1",
        namespace="default",
        plural="jobs",
        body=vcjob
    )
    return api_response


def create_image_builder_vcjob(job_in: ImageBuilderJob, id: int):
    config.load_incluster_config()
    api = client.CustomObjectsApi()
    tasks = [{
        "replicas": 1,
        "name": "image-builder",
        "template": {
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
    }]
    vcjob = {
        "apiVersion": "batch.volcano.sh/v1alpha1",
        "kind": "Job",
        "metadata": {
            "name": "pinta-job-" + str(id)
        },
        "spec": {
            "minAvailable": 1,
            "schedulerName": "volcano",
            "plugins": {"env": [], "svc": []},
            "policies": [{"event": "PodEvicted", "action": "RestartJob"}],
            "tasks": tasks
        }
    }
    api_response = api.create_namespaced_custom_object(
        group="batch.volcano.sh",
        version="v1alpha1",
        namespace="default",
        plural="jobs",
        body=vcjob
    )
    return api_response


def commit_image_builder(name: str, id: int, username: str):
    config.load_incluster_config()
    api = client.CoreV1Api()
    exec_command = [
        "/bin/sh",
        "-c",
        f"docker commit image-builder-container registry-service.pinta-system.svc:5000/{username}/{name}; "
        f"docker push registry-service.pinta-system.svc:5000/{username}/{name}"
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
        group="batch.volcano.sh",
        version="v1alpha1",
        namespace="default",
        plural="jobs",
        name="pinta-job-" + str(id)
    )
    return api_response


async def tunnel1(ws: WebSocket, resp: websockets.WebSocketClientProtocol):
    while True:
        data = await ws.receive_bytes()
        await resp.send(data)


async def tunnel2(resp: websockets.WebSocketClientProtocol, ws: WebSocket):
    terminate = False
    while not terminate:
        data = await resp.recv()
        await ws.send_bytes(data)


async def proxy(ws: WebSocket, name: str, command: List[str], container: Optional[str] = None):
    config.load_incluster_config()
    api = client.CoreV1Api()
    call_args = stream(api.connect_get_namespaced_pod_exec,
                       name=name,
                       namespace="default",
                       command=command,
                       container=container,
                       stderr=True, stdin=True,
                       stdout=True, tty=True,
                       _preload_content=False)
    async with websockets.connect(**call_args) as resp:
        t1 = asyncio.create_task(tunnel1(ws, resp))
        t2 = asyncio.create_task(tunnel2(resp, ws))
        try:
            await asyncio.gather(t1, t2)
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except WebSocketDisconnect:
            pass
