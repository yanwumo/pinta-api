from typing import Optional

from pydantic import BaseModel, Field


# Shared properties
class ImageBase(BaseModel):
    name: Optional[str] = Field(None, description="Image name.")
    description: Optional[str] = Field(None, description="Image description.")
    is_public: bool = Field(False, description="Indicates if the image is available for other users to use.")


# Properties to receive on image creation
class ImageCreate(ImageBase):
    name: str


# Properties to receive on image update
class ImageUpdate(ImageBase):
    pass


# Properties shared by models stored in DB
class ImageInDBBase(ImageBase):
    id: int
    name: str
    owner_id: int

    class Config:
        orm_mode = True


# Properties to return to client
class Image(ImageInDBBase):
    pass


# Properties stored in DB
class ImageInDB(ImageInDBBase):
    pass
