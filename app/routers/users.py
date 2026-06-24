from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.templating import templates
from ..core.web import add_flash, get_current_user, require_admin
from ..db import get_db
from ..services import users as user_service

router = APIRouter()


@router.get("/users")
def user_list(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request, name="users.html",
        context={"users": user_service.list_users(db), "current_user": get_current_user(request, db), "active_nav": "users"},
    )


@router.get("/users/new")
def user_new_page(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request, name="user_new.html",
        context={"error": "", "current_user": get_current_user(request, db), "active_nav": "users"},
    )


@router.post("/users/new")
def user_new_submit(
    request: Request,
    username: str = Form(...), password: str = Form(...), confirm_password: str = Form(...),
    is_admin: str = Form("false"), db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    user, error = user_service.create_user(db, username, password, confirm_password, is_admin == "true")
    if error:
        return templates.TemplateResponse(
            request=request, name="user_new.html",
            context={"error": error, "current_user": current_user, "active_nav": "users"}, status_code=400,
        )
    add_flash(request, f"用户 {user.username} 已创建", "success")
    return RedirectResponse(url="/users", status_code=303)


@router.get("/users/{user_id}/edit")
def user_edit_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    user = user_service.get_user(db, user_id)
    if user is None:
        return templates.TemplateResponse(
            request=request, name="not_found.html",
            context={"message": f"用户 ID {user_id} 不存在", "current_user": current_user}, status_code=404,
        )
    return templates.TemplateResponse(
        request=request, name="user_edit.html",
        context={"user_obj": user, "error": "", "current_user": current_user, "active_nav": "users"},
    )


@router.post("/users/{user_id}/edit")
def user_edit_submit(
    request: Request, user_id: int, username: str = Form(...),
    is_active: str = Form("true"), is_admin: str = Form("false"),
    new_password: str = Form(""), confirm_password: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    user = user_service.get_user(db, user_id)
    if user is None:
        return RedirectResponse(url="/users", status_code=303)
    error = user_service.update_user(
        db, user, username, is_active == "true", is_admin == "true",
        new_password, confirm_password, current_user,
    )
    if error:
        return templates.TemplateResponse(
            request=request, name="user_edit.html",
            context={"user_obj": user, "error": error, "current_user": current_user, "active_nav": "users"}, status_code=400,
        )
    if current_user and current_user.id == user.id:
        request.session["user"] = user.username
    add_flash(request, f"用户 {user.username} 已保存", "success")
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/{user_id}/delete")
def user_delete(request: Request, user_id: int, db: Session = Depends(get_db)):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    username = user_service.delete_user(db, user_service.get_user(db, user_id), current_user)
    if username:
        add_flash(request, f"用户 {username} 已删除", "success")
    else:
        add_flash(request, "不能删除当前登录用户", "warning")
    return RedirectResponse(url="/users", status_code=303)
