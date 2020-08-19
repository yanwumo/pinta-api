from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from sqlalchemy.orm import Session

from pinta.api import crud, models, schemas
from pinta.api.api import deps
from pinta.api.api.endpoints.util import patch_job_volumes, patch_job_image, patch_job_status, websocket_auth
from pinta.api.core.config import settings
from pinta.api.schemas import JobType

from pinta.api.kubernetes.job import create_pintajob, commit_image_builder, delete_pintajob, get_pintajob_log
from pinta.api.kubernetes.websocket import exec_proxy, log_proxy
from kubernetes.client.rest import ApiException

router = APIRouter()


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
        patch_job_status(job)
    return jobs


def create_job(db: Session, job_in: schemas.BaseSpec, current_user: models.User) -> Any:
    """
    Create a new job with symmetric node configurations.
    """
    if job_in.from_private:
        job_in.image = patch_job_image(db, job_in.image, current_user)
    job = crud.job.create_with_owner(db=db, obj_in=job_in, owner_id=current_user.id)
    if job.scheduled:
        try:
            volumes = patch_job_volumes(db, job.volumes, current_user.id)
            create_pintajob(job, volumes)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
            job = crud.job.remove(db=db, id=job.id)
            raise
    return job


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
    return create_job(db, job_in, current_user)


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
    return create_job(db, job_in, current_user)


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
    return create_job(db, job_in, current_user)


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
    return create_job(db, job_in, current_user)


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
            volumes = patch_job_volumes(db, job_in.volumes, current_user.id)
            create_pintajob(job_in, volumes)
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
        patch_job_status(job)
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
    delete_pintajob(id)
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
        volumes = patch_job_volumes(db, job.volumes, current_user.id)
        create_pintajob(job, volumes)
    except ApiException as e:
        print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
        raise
    job = crud.job.update(db=db, db_obj=job, obj_in=dict(scheduled=True))
    return job


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
        current_user = await websocket_auth(db, authorization)
        job = crud.job.get(db=db, id=id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
            raise HTTPException(status_code=400, detail="Not enough permissions")
        if job.type != JobType.image_builder:
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
        await exec_proxy(websocket, **args)
        await websocket.close()

        image = crud.image.create_with_owner(
            db=db,
            obj_in=schemas.ImageCreate(
                name=image_name
            ),
            owner_id=current_user.id)
        delete_pintajob(id)
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
    if job.type != JobType.image_builder:
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
    delete_pintajob(id)
    job = crud.job.remove(db=db, id=id)
    return image


@router.websocket("/{id}/exec")
async def exec_job(
    *,
    websocket: WebSocket,
    db: Session = Depends(deps.get_db),
    id: int,
    role: str = "",
    num: int = 0,
    tty: bool,
    command: str = "",
    authorization: str
):
    await websocket.accept()
    try:
        current_user = await websocket_auth(db, authorization)
        job = crud.job.get(db=db, id=id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
            raise HTTPException(status_code=400, detail="Not enough permissions")
        if not job.scheduled:
            raise HTTPException(status_code=400, detail="Job not scheduled")

        args = {"tty": tty}
        if role == "":
            role = JobType.replica_role(job.type)
        args["pod"] = f"pinta-job-{id}-{role}-{num}"
        if command == "":
            command = "if [ -e /bin/bash ]; then /bin/bash; else /bin/sh; fi"
        if job.type == JobType.image_builder:
            args["container"] = "docker-cli"
            command = f"docker exec -i{'t' if tty else ''} image-builder-container /bin/sh -c \"{command}\"; exit"
        args["command"] = [
            "/bin/sh",
            "-c",
            command
        ]

        await exec_proxy(websocket, **args)
        await websocket.close()
    except HTTPException as e:
        # Redirect HTTPException information to channel 3 (ERROR_CHANNEL)
        await websocket.send_bytes(bytes([3]) + f"HTTP {e.status_code}: {e.detail}".encode())
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


@router.get("/{id}/log")
def read_job_log(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    role: str = "",
    num: int = 0,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get the log of the job.
    """
    job = crud.job.get(db=db, id=id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    if not job.scheduled:
        raise HTTPException(status_code=400, detail="Job not scheduled")

    if role == "":
        role = JobType.replica_role(job.type)
    log = get_pintajob_log(id, role, num)
    return log


@router.websocket("/{id}/watch")
async def watch_job(
    *,
    websocket: WebSocket,
    db: Session = Depends(deps.get_db),
    id: int,
    role: str = "",
    num: int = 0,
    authorization: str
):
    await websocket.accept()
    try:
        current_user = await websocket_auth(db, authorization)
        job = crud.job.get(db=db, id=id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
            raise HTTPException(status_code=400, detail="Not enough permissions")
        if not job.scheduled:
            raise HTTPException(status_code=400, detail="Job not scheduled")

        if role == "":
            role = JobType.replica_role(job.type)
        await log_proxy(websocket, pod=f"pinta-job-{id}-{role}-{num}")
        await websocket.close()
    except HTTPException as e:
        # Redirect HTTPException information to channel 3 (ERROR_CHANNEL)
        await websocket.send_bytes(bytes([3]) + f"HTTP {e.status_code}: {e.detail}".encode())
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
