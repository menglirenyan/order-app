from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.templating import templates
from ..core.web import add_flash, get_current_user, require_admin, require_login, safe_redirect_path
from ..db import get_db
from ..models import Order
from ..services.printing import (
    get_delivery_print_config,
    prepare_print_job,
    set_delivery_print_config,
    split_lines,
)

router = APIRouter()


@router.post("/orders/{order_id}/print")
def mark_order_printed(
    request: Request,
    order_id: int,
    return_to: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        add_flash(request, "订单不存在，无法打印出货单", "error")
        return RedirectResponse(url="/orders", status_code=303)
    job = prepare_print_job(db, [order], current_user.username if current_user else "")
    if job["printed"]:
        add_flash(request, f"订单 {order.order_no} 已打印出货单，并标记为已拉走", "success")
        return templates.TemplateResponse(
            request=request,
            name="delivery_print_a4.html",
            context={
                "orders": job["orders"], "print_config": job["print_config"],
                "current_user": current_user, "auto_print": True,
                "return_to": safe_redirect_path(return_to, f"/orders/{order_id}"),
            },
        )
    add_flash(request, f"订单 {order.order_no} 已打印，不再重复标记", "warning")
    return RedirectResponse(url=safe_redirect_path(return_to, f"/orders/{order_id}"), status_code=303)


@router.post("/orders/batch-print")
def batch_print_orders(
    request: Request,
    order_ids: list[int] = Form(default=[]),
    return_to: str = Form("/orders"),
    db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    if order_ids:
        orders = db.query(Order).filter(Order.id.in_(order_ids)).order_by(Order.order_no.asc()).all()
        job = prepare_print_job(db, orders, current_user.username if current_user else "")
        if job["printed"]:
            return templates.TemplateResponse(
                request=request,
                name="delivery_print_a4.html",
                context={
                    "orders": job["orders"], "print_config": job["print_config"],
                    "current_user": current_user, "auto_print": True,
                    "return_to": safe_redirect_path(return_to, "/orders"),
                },
            )
        add_flash(request, "所选订单均已打印，未生成新的出货单", "warning")
    else:
        add_flash(request, "请先选择要发送打印的订单", "warning")
    return RedirectResponse(url=safe_redirect_path(return_to, "/orders"), status_code=303)


@router.get("/print-settings")
def print_settings_page(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    config = get_delivery_print_config(db)
    return templates.TemplateResponse(
        request=request,
        name="print_settings.html",
        context={
            "current_user": get_current_user(request, db), "print_config": config,
            "copies_text": "\n".join(config["copies"]),
            "footer_lines_text": "\n".join(config["footer_lines"]),
            "active_nav": "print_settings",
        },
    )


@router.post("/print-settings/delivery-config")
def update_delivery_print_config(
    request: Request,
    title: str = Form(""), copies_text: str = Form(""), unit: str = Form(""),
    footer_lines_text: str = Form(""), delivery_person_label: str = Form(""),
    delivery_person_value: str = Form(""), receiver_sign_label: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request, db)
    if redirect:
        return redirect
    set_delivery_print_config(db, {
        "title": title, "copies": split_lines(copies_text), "unit": unit,
        "footer_lines": split_lines(footer_lines_text),
        "delivery_person_label": delivery_person_label,
        "delivery_person_value": delivery_person_value,
        "receiver_sign_label": receiver_sign_label,
    })
    add_flash(request, "A4 出货单文案已保存", "success")
    return RedirectResponse(url="/print-settings", status_code=303)
