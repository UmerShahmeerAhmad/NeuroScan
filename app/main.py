"""
NeuroScan AI: application entry point.

Run from the project root (the folder that contains "app"):
    uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app import models
from app.auth import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.ml.model_loader import ensure_loaded
from app.routers import admin_routes, auth_routes, doctor_routes, pages

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("neuroscan")


def seed_admin() -> None:
    """Creates the administrator from the .env values if it does not exist yet."""
    with SessionLocal() as db:
        exists = db.query(models.User).filter(models.User.email == settings.ADMIN_EMAIL).first()
        if exists:
            return
        db.add(
            models.User(
                full_name=settings.ADMIN_NAME,
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role=models.ROLE_ADMIN,
                status=models.STATUS_APPROVED,
                institution="NeuroScan AI",
                designation="Administrator",
            )
        )
        db.commit()
        log.info("Administrator account created for %s", settings.ADMIN_EMAIL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts.
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        Base.metadata.create_all(bind=engine)  # creates the tables if they are missing
    except OperationalError:
        log.error(
            "Could not connect to the database. Check that PostgreSQL is running and that "
            "DATABASE_URL in .env has the right user, password, host and database name."
        )
        raise
    seed_admin()
    ensure_loaded()  # try to load the model now; if it fails the site still starts
    yield


app = FastAPI(
    title="NeuroScan AI",
    version="1.0.0",
    description="Brain tumor MRI classification for verified doctors.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# Only css/ and js/ are public. static/uploads/ is NOT mounted, so uploaded
# MRI images can only be fetched through the authenticated API.
app.mount("/static/css", StaticFiles(directory=settings.STATIC_DIR / "css"), name="css")
app.mount("/static/js", StaticFiles(directory=settings.STATIC_DIR / "js"), name="js")

app.include_router(pages.router)
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(doctor_routes.router)


@app.get("/api/health", tags=["System"])
def health():
    return {"status": "ok"}
