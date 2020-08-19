from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import relationship

from pinta.api.db.base_class import Base

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, index=True)
    is_public = Column(Boolean)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="images")
