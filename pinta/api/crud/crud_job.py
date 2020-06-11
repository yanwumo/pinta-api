from typing import List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from pinta.api.crud.base import CRUDBase
from pinta.api.models.job import Job
from pinta.api.schemas.job import JobCreate, JobUpdate, SymmetricJob, ImageBuilderJob


class CRUDJob(CRUDBase[Job, JobCreate, JobUpdate]):
    def create_with_owner(
        self, db: Session, *, obj_in: SymmetricJob, owner_id: int
    ) -> Job:
        # obj_in_data = jsonable_encoder(obj_in)
        # db_obj = self.model(**obj_in_data, owner_id=owner_id)
        db_obj = Job(name=obj_in.name, description=obj_in.description, type="symmetric", image=obj_in.image,
                     working_dir=obj_in.working_dir, replica_command=obj_in.command,
                     min_num_replicas=obj_in.min_num_replicas, max_num_replicas=obj_in.max_num_replicas,
                     ports=obj_in.ports, scheduled=obj_in.scheduled, owner_id=owner_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_image_builder_job_with_owner(
        self, db: Session, *, obj_in: ImageBuilderJob, owner_id: int
    ) -> Job:
        db_obj = Job(name=obj_in.name, description=obj_in.description, type="image_builder", image=obj_in.from_image,
                     min_num_replicas=1, max_num_replicas=1, scheduled=obj_in.scheduled, owner_id=owner_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Job]:
        return (
            db.query(self.model)
            .filter(Job.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )


job = CRUDJob(Job)
