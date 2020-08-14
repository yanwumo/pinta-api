from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from pinta.api.crud.base import CRUDBase
from pinta.api.models.image import Image
from pinta.api.schemas.image import ImageCreate, ImageUpdate


class CRUDImage(CRUDBase[Image, ImageCreate, ImageUpdate]):
    def create_with_owner(
        self, db: Session, *, obj_in: ImageCreate, owner_id: int
    ) -> Image:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data, owner_id=owner_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Image]:
        return (
            db.query(self.model)
            .filter(Image.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_owner_and_name(
        self, db: Session, *, current_user_id: int, owner_and_name: str
    ) -> Optional[Image]:
        delim = owner_and_name.split("/", 1)
        if len(delim) == 1:
            return (
                db.query(self.model)
                .filter(Image.owner_id == current_user_id, Image.name == owner_and_name)
                .first()
            )
        elif len(delim) == 2:
            username, image_name = delim[0], delim[1]
            return (
                db.query(self.model)
                .filter(Image.owner.username == username, Image.name == image_name)
                .first()
            )


image = CRUDImage(Image)
