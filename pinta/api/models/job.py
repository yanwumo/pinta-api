from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Enum, Boolean
from sqlalchemy.orm import relationship

from pinta.api.db.base_class import Base
from pinta.api.schemas.job import JobType

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class Job(Base):
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, index=True)
    type = Column(Enum(JobType))
    image = Column(String, index=True)
    volumes = Column(String)
    working_dir = Column(String)
    master_command = Column(String)
    replica_command = Column(String)
    num_masters = Column(Integer)
    num_replicas = Column(Integer)
    ports = Column(String)
    scheduled = Column(Boolean)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="jobs")
