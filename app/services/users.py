import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..core.security import hash_password
from ..models import User


logger = logging.getLogger(__name__)


def list_users(db: Session):
    return db.query(User).order_by(User.id.asc()).all()


def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, username: str, password: str, confirm_password: str, is_admin: bool):
    username = username.strip()
    if not username:
        return None, "用户名不能为空"
    if password != confirm_password:
        return None, "两次输入的密码不一致"
    if db.query(User).filter(User.username == username).first() is not None:
        return None, "用户名已存在"
    user = User(username=username, password_hash=hash_password(password), is_active=True, is_admin=is_admin)
    db.add(user)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to create user %s", username)
        return None, "用户保存失败，请联系管理员检查数据库写入权限"
    db.refresh(user)
    return user, ""


def update_user(
    db: Session,
    user: User,
    username: str,
    is_active: bool,
    is_admin: bool,
    new_password: str,
    confirm_password: str,
    current_user: User | None,
):
    username = username.strip()
    if not username:
        return "用户名不能为空"
    duplicate = db.query(User).filter(User.username == username, User.id != user.id).first()
    if duplicate is not None:
        return "用户名已存在"
    if new_password or confirm_password:
        if new_password != confirm_password:
            return "两次输入的新密码不一致"
        user.password_hash = hash_password(new_password)
    user.username = username
    user.is_active = is_active
    user.is_admin = is_admin
    if current_user and current_user.id == user.id:
        user.is_active = True
        user.is_admin = True
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to update user %s", username)
        return "用户保存失败，请联系管理员检查数据库写入权限"
    return ""


def delete_user(db: Session, user: User | None, current_user: User | None):
    if user is None or current_user and user.id == current_user.id:
        return None
    username = user.username
    db.delete(user)
    db.commit()
    return username
