from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from sqlalchemy.orm import Session

from pinta.api import crud, models, schemas
from pinta.api.api import deps

from pinta.api.kubernetes.job import get_vcjob, create_vcjob, create_image_builder_vcjob, commit_image_builder, proxy
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
    job = crud.job.create_with_owner(db=db, obj_in=job_in, owner_id=current_user.id)
    if job_in.scheduled:
        try:
            create_vcjob(job_in=job_in, id=job.id)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
            job = crud.job.remove(db=db, id=job.id)
            raise
    return job


@router.post("/image_builder", response_model=schemas.Job)
def create_image_builder_job(
    *,
    db: Session = Depends(deps.get_db),
    job_in: schemas.ImageBuilderJob,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new job which builds a new image.
    """
    job = crud.job.create_image_builder_job_with_owner(db=db, obj_in=job_in, owner_id=current_user.id)
    if job_in.scheduled:
        try:
            create_image_builder_vcjob(job_in=job_in, id=job.id)
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
            create_vcjob(job_in=job_in, id=job.id)
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
        create_vcjob(job_in=job, id=job.id)
    except ApiException as e:
        print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
        raise
    job = crud.job.update(db=db, db_obj=job, obj_in=dict(scheduled=True))
    return job


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
    commit_image_builder(name=image_name, id=id, username=current_user.email)
    job = crud.job.remove(db=db, id=id)
    return job


@router.websocket("/{id}/exec")
async def exec_job(
    *,
    websocket: WebSocket,
    db: Session = Depends(deps.get_db),
    id: int,
    authorization: str
):
    class Headers:
        def __init__(self, auth):
            self.auth = auth

        def get(self, _):
            return self.auth

    class Request:
        def __init__(self, auth):
            self.headers = Headers(auth)

    request = Request(authorization)
    param = await deps.reusable_oauth2(request)
    current_user: models.User = deps.get_current_active_user(deps.get_current_user(db=db, token=param))

    job = crud.job.get(db=db, id=id)
    if not job:
        # raise HTTPException(status_code=404, detail="Job not found")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not crud.user.is_superuser(current_user) and (job.owner_id != current_user.id):
        # raise HTTPException(status_code=400, detail="Not enough permissions")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not job.scheduled:
        # raise HTTPException(status_code=400, detail="Job not scheduled")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if job.type == "image_builder":
        args = dict(
            name=f"pinta-job-{id}-image-builder-0",
            container="docker-cli",
            command=[
                "/bin/sh",
                "-c",
                f"docker exec -it image-builder-container /bin/sh; exit"
            ]
        )
    else:
        args = dict(
            name=f"pinta-job-{id}-replica-0",
            command=["/bin/sh"]
        )

    await websocket.accept()
    try:
        await proxy(websocket, **args)
    finally:
        await websocket.close()