from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from kubernetes.client.rest import ApiException
from sqlalchemy.orm import Session

from pinta.api import crud, models, schemas
from pinta.api.api import deps
from pinta.api.kubernetes.volume import create_pvc, delete_pvc

router = APIRouter()


@router.get("/", response_model=List[schemas.Volume])
def read_volumes(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve volumes.
    """
    if crud.user.is_superuser(current_user):
        volumes = crud.volume.get_multi(db, skip=skip, limit=limit)
    else:
        volumes = crud.volume.get_multi_by_owner(
            db=db, owner_id=current_user.id, skip=skip, limit=limit
        )
    return volumes


@router.post("/", response_model=schemas.Volume)
def create_volume(
    *,
    db: Session = Depends(deps.get_db),
    volume_in: schemas.VolumeCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new volume.
    """
    volume = crud.volume.create_with_owner(db=db, obj_in=volume_in, owner_id=current_user.id)
    try:
        create_pvc(volume)
    except ApiException as e:
        print("Exception when calling CustomObjectsApi->create_cluster_custom_object: %s\n" % e)
        volume = crud.volume.remove(db=db, id=volume.id)
        raise
    return volume


@router.get("/{id}", response_model=schemas.Volume)
def read_volume(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get volume by ID.
    """
    volume = crud.volume.get(db=db, id=id)
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")
    if not crud.user.is_superuser(current_user) and (volume.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return volume


@router.delete("/{id}", response_model=schemas.Volume)
def delete_volume(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a volume.
    """
    volume = crud.volume.get(db=db, id=id)
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")
    if not crud.user.is_superuser(current_user) and (volume.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    delete_pvc(volume)
    volume = crud.volume.remove(db=db, id=id)
    return volume
