from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class JobType(str, Enum):
    ps_worker = "ps-worker"
    mpi = "mpi"
    symmetric = "symmetric"
    image_builder = "image-builder"

    @classmethod
    def master_role(cls, type):
        d = {
            cls.ps_worker: "ps",
            cls.mpi: "master",
            cls.symmetric: None,
            cls.image_builder: None
        }
        return d[type]

    @classmethod
    def replica_role(cls, type):
        d = {
            cls.ps_worker: "worker",
            cls.mpi: "replica",
            cls.symmetric: "replica",
            cls.image_builder: "image-builder"
        }
        return d[type]


# Shared properties
class BaseSpec(BaseModel):
    name: str = Field(..., description="Job name.")
    description: Optional[str] = Field(None, description="Job description.")


class SymmetricJobSpec(BaseModel):
    """
    Specification of a symmetric job.
    """
    image: str = Field(..., description="Image deployed when the job runs, possibly with tags. It can be a docker "
                                        "image from a publicly available repository (e.g., alpine:latest, "
                                        "tensorflow/tensorflow), or an image that is created and stored in the "
                                        "system.")
    from_private: bool = Field(True, description="Set to true if fetch the image from local registry.")
    volumes: str = Field(..., description="A list of volume names that are attached to the job, separated by comma. "
                                          "It can be a combination of private volumes created by the user "
                                          "(e.g. mnist), and/or volumes shared publicly by other users "
                                          "(e.g. admin/imagenet).")
    working_dir: str = Field(..., description="Working directory when running the command.")
    command: str = Field(..., description="Command to run.")
    num_replicas: int
    ports: str = Field(..., description="Ports to expose.")
    schedule: bool = Field(True, description="If set to false, job will be put into pending state. Use PATCH to change"
                                              "later on. If set to true, job will be immediately queued to the system, "
                                              "waiting to be scheduled.")


class SymmetricJob(SymmetricJobSpec, BaseSpec):
    """
    All nodes in a symmetric job have identical configuration,
    with the only difference being node index.
    """
    @property
    def type(self):
        return JobType.symmetric

    @property
    def master_command(self):
        return None

    @property
    def replica_command(self):
        return self.command

    @property
    def num_masters(self):
        return None

    @property
    def num_replicas(self):
        return self.num_replicas

    @property
    def scheduled(self):
        return self.schedule


class PSWorkerJobSpec(BaseModel):
    """
    Specification of a ps-worker job.
    """
    image: str = Field(..., description="Image deployed when the job runs, possibly with tags. It can be a docker "
                                        "image from a publicly available repository (e.g., alpine:latest, "
                                        "tensorflow/tensorflow), or an image that is created and stored in the "
                                        "system.")
    from_private: bool = Field(True, description="Set to true if fetch the image from local registry.")
    volumes: str = Field(..., description="A list of volume names that are attached to the job, separated by comma. "
                                          "It can be a combination of private volumes created by the user "
                                          "(e.g. mnist), and/or volumes shared publicly by other users "
                                          "(e.g. admin/imagenet).")
    working_dir: str = Field(..., description="Working directory when running the command.")
    ps_command: str = Field(..., description="Command to run on parameter server.")
    worker_command: str = Field(..., description="Command to run on worker.")
    num_ps: int
    num_workers: int
    ports: str = Field(..., description="Ports to expose.")
    schedule: bool = Field(True, description="If set to false, job will be put into pending state. Use PATCH to "
                                              "change later on. If set to true, job will be immediately queued to "
                                              "the system, waiting to be scheduled.")


class PSWorkerJob(PSWorkerJobSpec, BaseSpec):
    """
    There are two types of nodes in a ps-worker job: parameter server and worker.
    """
    @property
    def type(self):
        return JobType.ps_worker

    @property
    def master_command(self):
        return self.ps_command

    @property
    def replica_command(self):
        return self.worker_command

    @property
    def num_masters(self):
        return self.num_ps

    @property
    def num_replicas(self):
        return self.num_workers

    @property
    def scheduled(self):
        return self.schedule


class MPIJobSpec(BaseModel):
    """
    Specification of an MPI job.
    """
    image: str = Field(..., description="Image deployed when the job runs, possibly with tags. It can be a docker "
                                        "image from a publicly available repository (e.g., alpine:latest, "
                                        "tensorflow/tensorflow), or an image that is created and stored in the "
                                        "system.")
    from_private: bool = Field(True, description="Set to true if fetch the image from local registry.")
    volumes: str = Field(..., description="A list of volume names that are attached to the job, separated by comma. "
                                          "It can be a combination of private volumes created by the user "
                                          "(e.g. mnist), and/or volumes shared publicly by other users "
                                          "(e.g. admin/imagenet).")
    working_dir: str = Field(..., description="Working directory when running the command.")
    master_command: str = Field(..., description="Command to run on master.")
    replica_command: str = Field(..., description="Command to run on replica.")
    num_replicas: int
    ports: str = Field(..., description="Ports to expose.")
    schedule: bool = Field(True, description="If set to false, job will be put into pending state. Use PATCH to "
                                              "change later on. If set to true, job will be immediately queued to "
                                              "the system, waiting to be scheduled.")


class MPIJob(MPIJobSpec, BaseSpec):
    """
    There are two types of nodes in an MPI job: master and replicas.
    """
    @property
    def type(self):
        return JobType.mpi

    @property
    def num_masters(self):
        return 1

    @property
    def scheduled(self):
        return self.schedule


class ImageBuilderJobSpec(BaseModel):
    """
    Specification of an image builder job.
    """
    from_image: str = Field(..., description="Image deployed when the job runs, possibly with tags. It can be a docker "
                                             "image from a publicly available repository (e.g., alpine:latest, "
                                             "tensorflow/tensorflow), or an image that is created and stored in the "
                                             "system.")
    from_private: bool = Field(True, description="Set to true if fetch the image from local registry.")
    volumes: str = Field(..., description="A list of volume names that are attached to the job, separated by comma. "
                                          "It can be a combination of private volumes created by the user "
                                          "(e.g. mnist), and/or volumes shared publicly by other users "
                                          "(e.g. admin/imagenet).")
    schedule: bool = True


class ImageBuilderJob(ImageBuilderJobSpec, BaseSpec):
    """
    An image builder job starts an instance using the specified base image. User can install packages,
    include files, and testrun code based on their needs. User packs the modified image and commits it
    to the local registry, so that the image can be used towards the real workload later on.
    """
    @property
    def type(self):
        return JobType.image_builder

    @property
    def image(self):
        return self.from_image

    @image.setter
    def image(self, value):
        self.from_image = value

    @property
    def working_dir(self):
        return None

    @property
    def master_command(self):
        return None

    @property
    def replica_command(self):
        return None

    @property
    def num_masters(self):
        return None

    @property
    def num_replicas(self):
        return 1

    @property
    def ports(self):
        return None

    @property
    def scheduled(self):
        return self.schedule


# Properties to receive on item creation
class JobCreate(BaseSpec):
    type: JobType
    spec: Union[SymmetricJobSpec, ImageBuilderJobSpec]


# Properties to receive on item update
class JobUpdate(JobCreate):
    pass


# Properties shared by models stored in DB
class JobInDBBase(BaseModel):
    """
    Specification of a job.
    """
    id: Optional[int] = None
    owner_id: Optional[int] = None
    name: Optional[str] = Field(None, description="Job name.")
    description: Optional[str] = Field(None, description="Job description.")
    type: Optional[JobType] = Field(None, description="Job type.")
    image: Optional[str] = Field(None, description="Image deployed when the job runs, possibly with tags. It can be a docker "
                                        "image from a publicly available repository (e.g., alpine:latest, "
                                        "tensorflow/tensorflow), or an image that is created and stored in the "
                                        "system.")
    volumes: Optional[str] = Field(None, description="A list of volume names that are attached to the job, separated by comma. "
                                          "It can be a combination of private volumes created by the user "
                                          "(e.g. mnist), and/or volumes shared publicly by other users "
                                          "(e.g. admin/imagenet).")
    working_dir: Optional[str] = Field(None, description="Working directory when running the command.")
    master_command: Optional[str] = None
    replica_command: Optional[str] = None
    num_masters: Optional[int] = None
    num_replicas: Optional[int] = None
    ports: Optional[str] = None
    scheduled: Optional[bool] = Field(None, description="If set to false, job will be put into pending state. Use PATCH to "
                                              "change later on. If set to true, job will be immediately queued to "
                                              "the system, waiting to be scheduled.")

    class Config:
        orm_mode = True


class JobStatus(str, Enum):
    scheduled = "scheduled"
    running = "running"
    completed = "completed"
    error = "error"


# Additional properties to return to client via API
class Job(JobInDBBase):
    pass


class JobWithStatus(Job):
    status: Optional[JobStatus] = None


# Additional properties stored in DB
class JobInDB(JobInDBBase):
    pass
