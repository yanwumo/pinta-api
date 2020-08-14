from typing import Optional

from pydantic import BaseModel, Field


# Shared properties
class VolumeBase(BaseModel):
    name: Optional[str] = Field(None, description="Volume name.")
    description: Optional[str] = Field(None, description="Volume description.")
    capacity: Optional[str] = Field(None, description="Volume capacity.")
    is_public: bool = Field(False, description="Indicates if the volume is available for other users to use.")


# Properties to receive on volume creation
class VolumeCreate(VolumeBase):
    name: str
    capacity: str


# Properties to receive on volume update
class VolumeUpdate(VolumeBase):
    pass


# Properties shared by models stored in DB
class VolumeInDBBase(VolumeBase):
    id: int
    name: str
    owner_id: int

    class Config:
        orm_mode = True


# Properties to return to client
class Volume(VolumeInDBBase):
    pass


# Properties properties stored in DB
class VolumeInDB(VolumeInDBBase):
    pass
