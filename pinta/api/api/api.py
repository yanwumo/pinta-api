from fastapi import APIRouter

from pinta.api.api.endpoints import utils, users, login, jobs, volumes, images

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(volumes.router, prefix="/volumes", tags=["volumes"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
