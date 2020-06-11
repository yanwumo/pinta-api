# Import all the models, so that Base has them before being
# imported by Alembic
from pinta.api.db.base_class import Base  # noqa
from pinta.api.models.user import User  # noqa
from pinta.api.models.job import Job  # noqa
