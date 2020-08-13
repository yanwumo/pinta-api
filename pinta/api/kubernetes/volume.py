from kubernetes import client, config

from pinta.api.schemas.volume import Volume
from pinta.api.core.config import settings


def create_pvc(volume: Volume):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    pvc = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(
            name=f"pinta-volume-{volume.id}"
        ),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteMany"],
            resources=client.V1ResourceRequirements(
                requests={
                    "storage": volume.capacity
                }
            ),
            storage_class_name=settings.STORAGE_CLASS_NAME
        )
    )
    api = client.CoreV1Api()
    api_response = api.create_namespaced_persistent_volume_claim(namespace="default", body=pvc)
    return api_response


def delete_pvc(volume: Volume):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CoreV1Api()
    api_response = api.delete_namespaced_persistent_volume_claim(name=f"pinta-volume-{volume.id}", namespace="default")
    return api_response
