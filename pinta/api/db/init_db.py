from sqlalchemy.orm import Session

from pinta.api import crud, schemas
from pinta.api.core.config import settings
from pinta.api.db import base  # noqa: F401

# make sure all SQL Alchemy models are imported (pinta.api.db.base) before initializing DB
# otherwise, SQL Alchemy might fail to initialize relationships properly
# for more details: https://github.com/tiangolo/full-stack-fastapi-postgresql/issues/28


def init_db(db: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next line
    # Base.metadata.create_all(bind=engine)
    from .base_class import Base
    # for tbl in reversed(Base.metadata.sorted_tables):
    #     # db.get_bind().execute(tbl.delete())
    #     tbl.drop(db.get_bind())
    Base.metadata.drop_all(bind=db.get_bind())
    Base.metadata.create_all(bind=db.get_bind())

    user = crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = schemas.UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.user.create(db, obj_in=user_in)  # noqa: F841
