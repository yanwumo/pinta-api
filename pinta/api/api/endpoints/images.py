from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from kubernetes.client.rest import ApiException
from sqlalchemy.orm import Session

from pinta.api import crud, models, schemas
from pinta.api.api import deps
from pinta.api.api.endpoints.jobs import create_image_builder_job

router = APIRouter()


@router.get("/", response_model=List[schemas.Image])
def read_images(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve images.
    """
    if crud.user.is_superuser(current_user):
        images = crud.image.get_multi(db, skip=skip, limit=limit)
    else:
        images = crud.image.get_multi_by_owner(
            db=db, owner_id=current_user.id, skip=skip, limit=limit
        )
    return images


@router.post("/", response_model=schemas.Job)
def create_image(
    *,
    db: Session = Depends(deps.get_db),
    job_in: schemas.ImageBuilderJob,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new job which builds a new image.
    """
    return create_image_builder_job(db=db, job_in=job_in, current_user=current_user)


# @router.put("/{id}", response_model=schemas.Image)
# def update_image(
#     *,
#     db: Session = Depends(deps.get_db),
#     id: int,
#     image_in: schemas.ImageUpdate,
#     current_user: models.User = Depends(deps.get_current_active_user),
# ) -> Any:
#     """
#     Update an image.
#     """
#     image = crud.image.get(db=db, id=id)
#     if not image:
#         raise HTTPException(status_code=404, detail="Image not found")
#     if not crud.user.is_superuser(current_user) and (image.owner_id != current_user.id):
#         raise HTTPException(status_code=400, detail="Not enough permissions")
#     image = crud.image.update(db=db, db_obj=image, obj_in=image_in)
#     return image


@router.get("/{id}", response_model=schemas.Image)
def read_image(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get image by ID.
    """
    image = crud.image.get(db=db, id=id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not crud.user.is_superuser(current_user) and (image.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return image


@router.delete("/{id}", response_model=schemas.Image)
def delete_image(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete an image.
    """
    image = crud.image.get(db=db, id=id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not crud.user.is_superuser(current_user) and (image.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    image = crud.image.remove(db=db, id=id)
    return image


# @router.patch("/{id}", response_model=schemas.Job)
# def commit_image(
#     *,
#     db: Session = Depends(deps.get_db),
#     id: int,
#     current_user: models.User = Depends(deps.get_current_active_user),
# ) -> Any:
#     """
#     Commit an image.
#     """
#     image = crud.image.get(db=db, id=id)
#     if not image:
#         raise HTTPException(status_code=404, detail="Image not found")
#     if not crud.user.is_superuser(current_user) and (image.owner_id != current_user.id):
#         raise HTTPException(status_code=400, detail="Not enough permissions")
#     if image.scheduled:
#         raise HTTPException(status_code=400, detail="Image already scheduled")
#     commit_image(image=image, id=image.id, username=current_user.email)
#     image = crud.image.update(db=db, db_obj=image, obj_in=dict(is_pending=False))
#     return image
