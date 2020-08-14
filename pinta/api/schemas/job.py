from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class JobType(str, Enum):
    ps_worker = "ps_worker"
    mpi = "mpi"
    symmetric = "symmetric"
    image_builder = "image_builder"


# Shared properties
class JobBase(BaseModel):
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
    scheduled: bool = Field(True, description="If set to false, job will be put into pending state. Use PATCH to change"
                                              "later on. If set to true, job will be immediately queued to the system, "
                                              "waiting to be scheduled.")


class SymmetricJob(SymmetricJobSpec, JobBase):
    """
    All nodes in a symmetric job have identical configuration,
    with the only difference being node index.
    """
    pass


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
    scheduled: bool = Field(True, description="If set to false, job will be put into pending state. Use PATCH to "
                                              "change later on. If set to true, job will be immediately queued to "
                                              "the system, waiting to be scheduled.")


class PSWorkerJob(PSWorkerJobSpec, JobBase):
    """
    There are two types of nodes in a ps-worker job: parameter server and worker.
    """
    pass


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
    scheduled: bool = Field(True, description="If set to false, job will be put into pending state. Use PATCH to "
                                              "change later on. If set to true, job will be immediately queued to "
                                              "the system, waiting to be scheduled.")


class MPIJob(MPIJobSpec, JobBase):
    """
    There are two types of nodes in an MPI job: master and replicas.
    """
    pass


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
    scheduled: bool = True


class ImageBuilderJob(ImageBuilderJobSpec, JobBase):
    """
    An image builder job starts an instance using the specified base image. User can install packages,
    include files, and testrun code based on their needs. User packs the modified image and commits it
    to the local registry, so that the image can be used towards the real workload later on.
    """
    pass


# Properties to receive on item creation
class JobCreate(JobBase):
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
