from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import models  # Register SQLAlchemy metadata before startup migrations.
from .core.config import settings
from .core.migrations import initialize_database
from .routers import auth, dashboard, orders, printing, showcase, system, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


def create_app() -> FastAPI:
    application = FastAPI(lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
    application.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
    application.include_router(auth.router)
    application.include_router(dashboard.router)
    application.include_router(printing.router)
    application.include_router(orders.router)
    application.include_router(showcase.router)
    application.include_router(users.router)
    application.include_router(system.router)
    return application


app = create_app()
