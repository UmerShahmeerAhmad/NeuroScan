"""Serves the HTML pages. The pages are public; the data behind them is protected by the API."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(include_in_schema=False)


def _page(filename: str) -> FileResponse:
    return FileResponse(
        settings.TEMPLATES_DIR / filename,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/")
def home():
    return _page("index.html")


@router.get("/login")
def login_page():
    return _page("login.html")


@router.get("/signup")
def signup_page():
    return _page("signup.html")


@router.get("/admin")
def admin_page():
    return _page("admin_dashboard.html")


@router.get("/doctor")
def doctor_page():
    return _page("doctor_dashboard.html")


@router.get("/forgot-password")
def forgot_password_page():
    return _page("forgot_password.html")


@router.get("/reset-password")
def reset_password_page():
    return _page("reset_password.html")
