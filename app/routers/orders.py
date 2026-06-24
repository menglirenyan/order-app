from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..core.templating import templates
from ..core.web import add_flash, get_current_user, require_login, safe_redirect_path
from ..db import get_db
from ..models import Order
from ..schemas.forms import OrderFormData, OrderListFilters
from ..services import orders as order_service
from ..services.printing import apply_print_delivery_snapshot
from ..services.voice import parse_voice_order, parse_voice_query
from ..utils.formatters import action_label

router = APIRouter()


def _form_data(
    customer, phone, order_type, item_name, size, quantity, unit_price, paid_amount, remark
):
    return OrderFormData(
        customer=customer, phone=phone, order_type=order_type, item_name=item_name,
        size=size, quantity=quantity, unit_price=unit_price,
        paid_amount=paid_amount, remark=remark,
    )


@router.get("/orders")
def order_list(
    request: Request,
    keyword: str = "",
    order_type: str = "",
    payment_status: str = "",
    delivery_status: str = "",
    print_status: str = "",
    date_from: str = "",
    date_to: str = "",
    sort_by: str = "risk_first",
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    filters = OrderListFilters(
        keyword, order_type, payment_status, delivery_status, print_status,
        date_from, date_to, sort_by, page, per_page,
    )
    result = order_service.list_orders(db, filters)
    for error in result.pop("date_errors"):
        add_flash(request, error, "error")
    normalized_payment = result.pop("normalized_payment")
    context = {
        **result,
        "keyword": keyword,
        "order_type": order_type,
        "payment_status": normalized_payment,
        "delivery_status": delivery_status,
        "print_status": print_status,
        "sort_by": sort_by,
        "current_user": get_current_user(request, db),
        "active_nav": "orders",
        "order_types": order_service.ORDER_TYPES,
    }
    return templates.TemplateResponse(request=request, name="orders.html", context=context)


@router.get("/api/suggest")
def suggest_values(request: Request, field: str, q: str = "", db: Session = Depends(get_db)):
    if require_login(request):
        return JSONResponse({"items": []}, status_code=401)
    allowed_fields = {"customer": Order.customer, "item_name": Order.item_name, "size": Order.size}
    if field not in allowed_fields:
        return {"items": []}
    return {"items": order_service.get_recent_distinct_values(db, allowed_fields[field], q.strip(), 20)}


@router.get("/api/recent-price")
def recent_price(request: Request, item_name: str = "", size: str = "", db: Session = Depends(get_db)):
    if require_login(request):
        return JSONResponse({"ok": False}, status_code=401)
    order = order_service.get_recent_price(db, item_name, size)
    if order is None:
        return {"ok": False}
    return {"ok": True, "unit_price": order.unit_price, "order_no": order.order_no}


@router.post("/api/voice-order-query-draft")
async def voice_order_query_draft(request: Request, db: Session = Depends(get_db)):
    if require_login(request):
        return JSONResponse({"ok": False, "message": "请先登录"}, status_code=401)
    payload = await request.json()
    text_value = str(payload.get("text") or "").strip()
    if not text_value:
        return JSONResponse({"ok": False, "message": "请输入语音识别后的查询内容"}, status_code=400)
    return parse_voice_query(db, text_value)


@router.post("/api/voice-order-draft")
async def voice_order_draft(request: Request, db: Session = Depends(get_db)):
    if require_login(request):
        return JSONResponse({"ok": False, "message": "请先登录"}, status_code=401)
    payload = await request.json()
    text_value = str(payload.get("text") or "").strip()
    if not text_value:
        return JSONResponse({"ok": False, "message": "请输入语音识别后的文字"}, status_code=400)
    return parse_voice_order(db, text_value)


@router.get("/orders/new")
def order_new(request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    context = {
        "next_order_no": order_service.generate_order_no(db),
        **order_service.get_order_form_options(db),
        "current_user": get_current_user(request, db),
        "form_data": {},
        "order_types": order_service.ORDER_TYPES,
        "active_nav": "order_new",
    }
    return templates.TemplateResponse(request=request, name="order_new.html", context=context)


@router.post("/orders")
def create_order(
    request: Request,
    customer: str = Form(...), phone: str = Form(""), order_type: str = Form("瓦楞板"),
    item_name: str = Form(...), size: str = Form(""), quantity: int = Form(...),
    unit_price: float = Form(...), paid_amount: float = Form(0.0), remark: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    data = _form_data(customer, phone, order_type, item_name, size, quantity, unit_price, paid_amount, remark)
    order, errors = order_service.create_order(db, data)
    if errors:
        form_values = data.__dict__.copy()
        form_values["order_type"] = order_service.normalize_order_type(order_type)
        context = {
            "next_order_no": order_service.generate_order_no(db),
            **order_service.get_order_form_options(db),
            "current_user": get_current_user(request, db),
            "order_types": order_service.ORDER_TYPES,
            "active_nav": "order_new",
            "form_data": form_values,
            "errors": errors,
        }
        return templates.TemplateResponse(request=request, name="order_new.html", context=context, status_code=400)
    add_flash(request, f"订单 {order.order_no} 已创建", "success")
    return RedirectResponse(url="/orders", status_code=303)


@router.get("/orders/{order_id}")
def order_detail(request: Request, order_id: int, db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        return templates.TemplateResponse(
            request=request, name="not_found.html",
            context={"message": f"订单 ID {order_id} 不存在", "current_user": current_user},
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request, name="order_detail.html",
        context={
            "order": order, "current_user": current_user, "active_nav": "orders",
            "logs": order_service.get_order_logs(db, order.id),
        },
    )


@router.get("/orders/{order_id}/edit")
def edit_order_page(request: Request, order_id: int, db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        return templates.TemplateResponse(
            request=request, name="not_found.html",
            context={"message": f"订单 ID {order_id} 不存在", "current_user": current_user},
            status_code=404,
        )
    context = {
        "order": order, **order_service.get_all_order_form_options(db),
        "current_user": current_user, "errors": [],
        "order_types": order_service.ORDER_TYPES, "active_nav": "orders",
    }
    return templates.TemplateResponse(request=request, name="order_edit.html", context=context)


@router.post("/orders/{order_id}/edit")
def edit_order_submit(
    request: Request, order_id: int,
    customer: str = Form(...), phone: str = Form(""), order_type: str = Form("瓦楞板"),
    item_name: str = Form(...), size: str = Form(""), quantity: int = Form(...),
    unit_price: float = Form(...), paid_amount: float = Form(0.0), remark: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        return RedirectResponse(url="/orders", status_code=303)
    current_user = get_current_user(request, db)
    data = _form_data(customer, phone, order_type, item_name, size, quantity, unit_price, paid_amount, remark)
    errors = order_service.update_order(db, order, data, current_user.username if current_user else "")
    if errors:
        form_values = data.__dict__.copy()
        form_values["order_type"] = order_service.normalize_order_type(order_type)
        context = {
            "order": order, **order_service.get_order_form_options(db),
            "current_user": current_user, "active_nav": "orders",
            "order_types": order_service.ORDER_TYPES, "errors": errors, "form_data": form_values,
        }
        return templates.TemplateResponse(request=request, name="order_edit.html", context=context, status_code=400)
    add_flash(request, f"订单 {order.order_no} 已保存", "success")
    return RedirectResponse(url=f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/paid")
def mark_order_paid(request: Request, order_id: int, return_to: str = Form(""), db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is not None:
        order_service.mark_paid(db, order, current_user.username if current_user else "")
        add_flash(request, f"订单 {order.order_no} 已标记结清，已收金额已同步为总金额", "success")
    else:
        add_flash(request, "订单不存在，无法标记付款", "error")
    return RedirectResponse(url=safe_redirect_path(return_to, f"/orders/{order_id}"), status_code=303)


@router.post("/orders/{order_id}/unpaid")
def mark_order_unpaid(request: Request, order_id: int, return_to: str = Form(""), db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is not None:
        order_service.mark_unpaid(db, order, current_user.username if current_user else "")
        add_flash(request, f"订单 {order.order_no} 已改回未结清", "success")
    else:
        add_flash(request, "订单不存在，无法改回未结清", "error")
    return RedirectResponse(url=safe_redirect_path(return_to, f"/orders/{order_id}"), status_code=303)


@router.post("/orders/{order_id}/payment")
def record_order_payment(
    request: Request, order_id: int, amount: str = Form(""), return_to: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        add_flash(request, "订单不存在，无法登记收款", "error")
    else:
        error = order_service.record_payment(db, order, amount, current_user.username if current_user else "")
        if error:
            add_flash(request, error, "error")
        else:
            add_flash(
                request,
                f"订单 {order.order_no} 已登记收款 {float(amount):.2f}，当前欠款 {order.unpaid_amount:.2f}",
                "success",
            )
    return RedirectResponse(url=safe_redirect_path(return_to, f"/orders/{order_id}"), status_code=303)


@router.post("/orders/{order_id}/delivered")
def mark_order_delivered(
    request: Request, order_id: int, return_to: str = Form(""), db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        add_flash(request, "订单不存在，无法标记拉走", "error")
    elif order_service.mark_delivered(db, order, current_user.username if current_user else ""):
        add_flash(request, f"订单 {order.order_no} 已标记拉走", "success")
    else:
        add_flash(request, f"订单 {order.order_no} 已经是拉走状态", "warning")
    return RedirectResponse(url=safe_redirect_path(return_to, f"/orders/{order_id}"), status_code=303)


@router.post("/orders/{order_id}/delete")
def delete_order(request: Request, order_id: int, db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is not None:
        order_no = order_service.delete_order(db, order, current_user.username if current_user else "")
        add_flash(request, f"订单 {order_no} 已删除", "success")
    else:
        add_flash(request, "订单不存在或已被删除", "warning")
    return RedirectResponse(url="/orders", status_code=303)


@router.post("/orders/{order_id}/undo")
def undo_last_order_action(request: Request, order_id: int, db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        add_flash(request, "订单不存在，无法撤回", "error")
        return RedirectResponse(url="/orders", status_code=303)
    log = order_service.undo_last_action(
        db, order, current_user.username if current_user else "", apply_print_delivery_snapshot
    )
    if log is None:
        add_flash(request, "没有可撤回的状态操作", "warning")
    else:
        add_flash(request, f"已撤回：{action_label(log.action)}", "success")
    return RedirectResponse(url=f"/orders/{order_id}", status_code=303)
