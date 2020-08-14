from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from sqlalchemy.orm import Session

from pinta.api import crud, models, schemas
from pinta.api.api import deps
from pinta.api.core.config import settings

from pinta.api.kubernetes.job import get_vcjob, create_symmetric_pintajob, create_ps_worker_pintajob, \
    create_mpi_pintajob, create_image_builder_pintajob, commit_image_builder, delete_vcjob
from pinta.api.kubernetes.websocket import proxy
from kubernetes.client.rest import ApiException

router = APIRouter()


def _translate_volumes(db: Session, volumes_in: str, current_user_id: int):
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


def _translate_image(db: Session, image_in: str, current_user: models.User):
    image = crud.image.get_by_owner_and_name(db, current_user_id=current_user.id, owner_and_name=image_in)
    if not image:
        raise HTTPException(status_code=404, detail=f"Image {image_in} does not exist")
    if len(image_in.split("/")) == 1:
        return f"localhost:30007/{current_user.username}/{image_in}"
    else:
        return f"localhost:30007/{settings.REGISTRY_SERVER}/{image_in}"


@router.get("/", response_model=List[schemas.JobWithStatus])
def read_jobs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve jobs.
    """
    if crud.user.is_superuser(current_user):
        jobs = crud.job.get_multi(db, skip=skip, limit=limit)
    else:
        jobs = crud.job.get_multi_by_owner(
            db=db, owner_id=current_user.id, skip=skip, limit=limit
        )
    for job in jobs:
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
    return jobs


@router.post("/", response_model=schemas.Job)
def create_job(
    *,
    db: Session = Depends(deps.get_db),
    job_in: schemas.SymmetricJob,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new job with symmetric node configurations.
    """
    return create_symmetric_job(db=db, job_in=job_in, current_user=current_user)


@router.post("/symmetric", response_model=schemas.Job)
def create_symmetric_job(
    *,
    db: Session = Depends(deps.get_db),
    job_in: schemas.SymmetricJob,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new job with symmetric node configurations.
    """
    if job_in.from_private:
        job_in.image = _translate_image(db, job_in.image, current_user)
    job = crud.job.create_symmetric_job_with_owner(db=db, obj_in=job_in, owner_id=current_user.id)
    if job_in.scheduled:
        try:
            job_in.volumes = _translate_volumes(db, job_in.volumes, current_user.id)
            create_symmetric_pintajob(job_in=job_in, id=job.id)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
            job = crud.job.remove(db=db, id=job.id)
            raise
    return job


@router.post("/ps-worker", response_model=schemas.Job)
def create_ps_worker_job(
    *,
    db: Session = Depends(deps.get_db),
    job_in: schemas.PSWorkerJob,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new job with parameter server and workers.
    """
    if job_in.from_private:
        job_in.image = _translate_image(db, job_in.image, current_user)
    job = crud.job.create_ps_worker_job_with_owner(db=db, obj_in=job_in, owner_id=current_user.id)
    if job_in.scheduled:
        try:
            job_in.volumes = _translate_volumes(db, job_in.volumes, current_user.id)
            create_ps_worker_pintajob(job_in=job_in, id=job.id)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
            job = crud.job.remove(db=db, id=job.id)
            raise
    return job


@router.post("/mpi", response_model=schemas.Job)
def create_mpi_job(
    *,
    db: Session = Depends(deps.get_db),
    job_in: schemas.MPIJob,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new job with master and replica node configurations, which are typically used by MPI.
    """
    if job_in.from_private:
        job_in.image = _translate_image(db, job_in.image, current_user)
    job = crud.job.create_mpi_job_with_owner(db=db, obj_in=job_in, owner_id=current_user.id)
    if job_in.scheduled:
        try:
            job_in.volumes = _translate_volumes(db, job_in.volumes, current_user.id)
            create_mpi_pintajob(job_in=job_in, id=job.id)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
            job = crud.job.remove(db=db, id=job.id)
            raise
    return job


@router.post("/image-builder", response_model=schemas.Job)
def create_image_builder_job(
    *,
    db: Session = Depends(deps.get_db),
    job_in: schemas.ImageBuilderJob,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new job which builds a new image.
    """
    if job_in.from_private:
        job_in.from_image = _translate_image(db, job_in.from_image, current_user)
    job = crud.job.create_image_builder_job_with_owner(db=db, obj_in=job_in, owner_id=current_user.id)
    if job_in.scheduled:
        try:
            job_in.volumes = _translate_volumes(db, job_in.volumes, current_user.id)
            create_image_builder_pintajob(job_in=job_in, id=job.id)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
            job = crud.job.remove(db=db, id=job.id)
            raise
    return job


@router.put("/{id}", response_model=schemas.Job)
def update_job(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    job_in: schemas.Job,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a job.
    """
    job = crud.job.get(db=db, id=id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    if job.scheduled:
        raise HTTPException(status_code=400, detail="Job already scheduled")
    if job_in.scheduled:
        try:
            job_in.volumes = _translate_volumes(db, job_in.volumes, current_user.id)
            if job.type == "ps_worker":
                create_ps_worker_pintajob(job_in=job, id=job.id)
            elif job.type == "mpi":
                create_mpi_pintajob(job_in=job, id=job.id)
            elif job.type == "symmetric":
                create_symmetric_pintajob(job_in=job, id=job.id)
            elif job.type == "image_builder":
                create_image_builder_pintajob(job_in=job, id=job.id)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
            job_in.scheduled = False
            raise
    job = crud.job.update(db=db, db_obj=job, obj_in=job_in)
    return job


@router.get("/{id}", response_model=schemas.JobWithStatus)
def read_job(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get job by ID.
    """
    job = crud.job.get(db=db, id=id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
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
    return job


@router.delete("/{id}", response_model=schemas.Job)
def delete_job(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a job.
    """
    job = crud.job.get(db=db, id=id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    delete_vcjob(id)
    job = crud.job.remove(db=db, id=id)
    return job


@router.patch("/{id}", response_model=schemas.Job)
def schedule_job(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Schedule a job.
    """
    job = crud.job.get(db=db, id=id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    if job.scheduled:
        raise HTTPException(status_code=400, detail="Job already scheduled")
    try:
        job.volumes = _translate_volumes(db, job.volumes, current_user.id)
        if job.type == "ps_worker":
            create_ps_worker_pintajob(job_in=job, id=job.id)
        elif job.type == "mpi":
            create_mpi_pintajob(job_in=job, id=job.id)
        elif job.type == "symmetric":
            create_symmetric_pintajob(job_in=job, id=job.id)
        elif job.type == "image_builder":
            create_image_builder_pintajob(job_in=job, id=job.id)
    except ApiException as e:
        print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
        raise
    job = crud.job.update(db=db, db_obj=job, obj_in=dict(scheduled=True))
    return job


# WebSocket interfaces
class Headers:
    def __init__(self, auth):
        self.auth = auth

    def get(self, _):
        return self.auth


class Request:
    def __init__(self, auth):
        self.headers = Headers(auth)


@router.websocket("/{id}/commit")
async def commit_image_builder_job(
    *,
    websocket: WebSocket,
    db: Session = Depends(deps.get_db),
    id: int,
    image_name: str,
    authorization: str
):
    """
    Commit an image.
    """
    await websocket.accept()
    try:
        request = Request(authorization)
        param = await deps.reusable_oauth2(request)
        current_user: models.User = deps.get_current_active_user(deps.get_current_user(db=db, token=param))

        job = crud.job.get(db=db, id=id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
            raise HTTPException(status_code=400, detail="Not enough permissions")
        if job.type != "image_builder":
            raise HTTPException(status_code=400, detail="Job is not an image builder")
        if not job.scheduled:
            raise HTTPException(status_code=400, detail="Image builder job not scheduled")

        args = dict(
            pod=f"pinta-job-{id}-image-builder-0",
            container="docker-cli",
            command=[
                "/bin/sh",
                "-c",
                f"docker commit image-builder-container {settings.REGISTRY_SERVER}/{current_user.username}/{image_name}; "
                f"docker push {settings.REGISTRY_SERVER}/{current_user.username}/{image_name}"
            ],
            tty=True
        )
        await proxy(websocket, **args)
        await websocket.close()

        image = crud.image.create_with_owner(
            db=db,
            obj_in=schemas.ImageCreate(
                name=image_name
            ),
            owner_id=current_user.id)
        delete_vcjob(id)
        job = crud.job.remove(db=db, id=id)
    except HTTPException as e:
        # Redirect HTTPException information to channel 3 (ERROR_CHANNEL)
        await websocket.send_bytes(bytes([3]) + f"HTTP {e.status_code}: {e.detail}".encode())
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


@router.post("/{id}/commit", response_model=schemas.Job)
def commit_job(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    image_name: str,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Commit an image.
    """
    job = crud.job.get(db=db, id=id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    if job.type != "image_builder":
        raise HTTPException(status_code=400, detail="Job is not an image builder")
    if not job.scheduled:
        raise HTTPException(status_code=400, detail="Image builder job not scheduled")
    commit_image_builder(name=image_name, id=id, username=current_user.username)

    image = crud.image.create_with_owner(
        db=db,
        obj_in=schemas.ImageCreate(
            name=image_name
        ),
        owner_id=current_user.id)
    delete_vcjob(id)
    job = crud.job.remove(db=db, id=id)
    return image


@router.websocket("/{id}/exec")
async def exec_job(
    *,
    websocket: WebSocket,
    db: Session = Depends(deps.get_db),
    id: int,
    tty: bool,
    command: str,
    authorization: str
):
    await websocket.accept()
    try:
        request = Request(authorization)
        param = await deps.reusable_oauth2(request)
        current_user: models.User = deps.get_current_active_user(deps.get_current_user(db=db, token=param))

        job = crud.job.get(db=db, id=id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
            raise HTTPException(status_code=400, detail="Not enough permissions")
        if not job.scheduled:
            raise HTTPException(status_code=400, detail="Job not scheduled")

        if job.type == "image_builder":
            args = dict(
                pod=f"pinta-job-{id}-image-builder-0",
                container="docker-cli",
                command=[
                    "/bin/sh",
                    "-c",
                    f"docker exec -i{'t' if tty else ''} image-builder-container {command}; exit"
                ],
                tty=tty
            )
        elif job.type == "ps_worker":
            args = dict(
                pod=f"pinta-job-{id}-worker-0",
                command=[
                    "/bin/sh",
                    "-c",
                    command
                ],
                tty=tty
            )
        else:
            args = dict(
                pod=f"pinta-job-{id}-replica-0",
                command=[
                    "/bin/sh",
                    "-c",
                    command
                ],
                tty=tty
            )
        await proxy(websocket, **args)
        await websocket.close()
    except HTTPException as e:
        # Redirect HTTPException information to channel 3 (ERROR_CHANNEL)
        await websocket.send_bytes(bytes([3]) + f"HTTP {e.status_code}: {e.detail}".encode())
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


# @router.websocket("/ws")
# async def test_websocket(websocket: WebSocket):
#     args = dict(
#         pod="nginx",
#         command=['tar', 'cf', '-', '/empty.txt']
#     )
#
#     await websocket.accept()
#     try:
#         await proxy(websocket, **args)
#     finally:
#         await websocket.close()
