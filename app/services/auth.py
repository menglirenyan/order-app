from sqlalchemy.orm import Session

from ..core.security import verify_password
from ..models import User


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username.strip()).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
