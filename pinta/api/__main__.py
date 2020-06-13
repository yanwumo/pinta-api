import uvicorn
from fastapi import FastAPI

from pinta.api.api.api_v1.api import api_router
from pinta.api.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME,
              openapi_url=f"{settings.API_STR}/openapi.json")
app.include_router(api_router, prefix=settings.API_STR)


def main():
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == '__main__':
    main()
