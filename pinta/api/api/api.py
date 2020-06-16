from fastapi import APIRouter

from pinta.api.api.endpoints import utils, users, login, jobs

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
# api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
