from fastapi import HTTPException, WebSocket
from kubernetes.client.rest import ApiException
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from pinta.api import crud, models
from pinta.api.api import deps
from pinta.api.core.config import settings
from pinta.api.kubernetes.job import get_vcjob


def patch_job_volumes(db: Session, volumes_in: str, current_user_id: int):
    volumes_out = []
    volumes_str = volumes_in.split(",")
    for volume_str in volumes_str:
        volume_str = volume_str.strip()
        if volume_str == "":
            continue
        volume = crud.volume.get_by_owner_and_name(db, current_user_id=current_user_id, owner_and_name=volume_str)
        if not volume:
            raise HTTPException(status_code=404, detail=f"Volume {volume_str} does not exist")
        volumes_out.append({
            "mountPath": f"/volumes/{volume.name}",
            "volumeClaimName": f"pinta-volume-{volume.id}",
        })
    return volumes_out


def patch_job_image(db: Session, image_in: str, current_user: models.User):
    image = crud.image.get_by_owner_and_name(db, current_user_id=current_user.id, owner_and_name=image_in)
    if not image:
        raise HTTPException(status_code=404, detail=f"Image {image_in} does not exist")
    if len(image_in.split("/")) == 1:
        return f"localhost:30007/{current_user.username}/{image_in}"
    else:
        return f"localhost:30007/{settings.REGISTRY_SERVER}/{image_in}"


def patch_job_status(job: models.Job):
    if job.scheduled:
        try:
            status = get_vcjob(job.id)["status"]["state"]["phase"]
            if status == "Pending":
                job.status = "scheduled"
            elif status == "Running":
                job.status = "running"
            elif status == "Completed":
                job.status = "completed"
            else:
                job.status = "error"
        except ApiException:
            job.status = "error"


# WebSocket interfaces
class Headers:
    def __init__(self, auth):
        self.auth = auth

    def get(self, _):
        return self.auth


class Request:
    def __init__(self, auth):
        self.headers = Headers(auth)


async def websocket_auth(db: Session, authorization: str) -> models.User:
    request = Request(authorization)
    param = await deps.reusable_oauth2(request)
    current_user = deps.get_current_active_user(deps.get_current_user(db=db, token=param))
    return current_user
