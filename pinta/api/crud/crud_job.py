from typing import List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from pinta.api.crud.base import CRUDBase
from pinta.api.models.job import Job
from pinta.api.schemas.job import JobCreate, JobUpdate, BaseSpec, PSWorkerJob, MPIJob, ImageBuilderJob


class CRUDJob(CRUDBase[Job, JobCreate, JobUpdate]):
    def create_with_owner(
        self, db: Session, *, obj_in: BaseSpec, owner_id: int
    ) -> Job:
        db_obj = Job(name=obj_in.name, description=obj_in.description, type=obj_in.type, image=obj_in.image,
                     volumes=obj_in.volumes, working_dir=obj_in.working_dir,
                     master_command=obj_in.master_command, num_masters=obj_in.num_masters,
                     replica_command=obj_in.replica_command, num_replicas=obj_in.num_replicas,
                     ports=obj_in.ports, scheduled=obj_in.scheduled, owner_id=owner_id)
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
