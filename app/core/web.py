from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..models import User


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def get_current_username(request: Request):
    return request.session.get("user")


def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def get_current_user(request: Request, db: Session):
    username = request.session.get("user")
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()


def require_admin(request: Request, db: Session):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    if current_user is None or not current_user.is_admin:
        return RedirectResponse(url="/orders", status_code=303)
    return None


def add_flash(request: Request, message: str, level: str = "success") -> None:
    flashes = list(request.session.get("flashes", []))
    flashes.append({"message": message, "level": level})
    request.session["flashes"] = flashes[-5:]


def get_flashes(request: Request):
    if hasattr(request.state, "flashes"):
        return request.state.flashes
    flashes = request.session.pop("flashes", [])
    request.state.flashes = flashes
    return flashes


def safe_redirect_path(return_to: str, default: str) -> str:
    return_to = str(return_to or "")
    if return_to.startswith("/") and not return_to.startswith("//"):
        return return_to
    return default
