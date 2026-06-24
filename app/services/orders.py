import json
import math
from datetime import date, datetime

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from ..models import OperationLog, Order
from ..schemas.forms import OrderFormData, OrderListFilters
from .audit import get_latest_reversible_log, log_operation

ORDER_TYPES = ["瓦楞板", "激光切割"]
PAYMENT_UNSETTLED = "未结清"
PAYMENT_SETTLED = "已结清"
DELIVERY_WAITING = "未拉走"
DELIVERY_DONE = "已拉走"


def generate_order_no(db: Session) -> str:
    today_prefix = datetime.now().strftime("%Y%m%d")
    today_orders = (
        db.query(Order)
        .filter(Order.order_no.like(f"{today_prefix}-%"))
        .order_by(Order.order_no.desc())
        .all()
    )
    if not today_orders:
        return f"{today_prefix}-001"
    last_seq = int(today_orders[0].order_no.split("-")[-1])
    return f"{today_prefix}-{last_seq + 1:03d}"


def normalize_order_type(value: str) -> str:
    value = str(value or "").strip()
    return value if value in ORDER_TYPES else "瓦楞板"


def normalize_payment_status(value: str) -> str:
    return PAYMENT_SETTLED if str(value or "").strip() in ["已结清", "已付款"] else PAYMENT_UNSETTLED


def normalize_delivery_status(value: str) -> str:
    value = str(value or "").strip()
    return value if value in [DELIVERY_WAITING, DELIVERY_DONE] else DELIVERY_WAITING


def calc_payment_status(total_amount: float, paid_amount: float, payment_status: str = PAYMENT_UNSETTLED):
    paid_amount = max(paid_amount or 0, 0)
    balance_due = max((total_amount or 0) - paid_amount, 0)
    payment_status = normalize_payment_status(payment_status)
    if payment_status == PAYMENT_SETTLED or (total_amount or 0) > 0 and paid_amount >= total_amount:
        return 0.0, PAYMENT_SETTLED
    return balance_due, PAYMENT_UNSETTLED


def parse_date_field(value: str, label: str):
    value = str(value or "").strip()
    if not value:
        return None, ""
    try:
        return date.fromisoformat(value), ""
    except ValueError:
        return None, f"{label}格式不正确，请使用日期选择器重新选择"


def validate_order_form(data: OrderFormData):
    errors = []
    if not str(data.customer or "").strip():
        errors.append("客户名称不能为空")
    if not str(data.item_name or "").strip():
        errors.append("商品名称不能为空")
    if normalize_order_type(data.order_type) != str(data.order_type or "").strip():
        errors.append("订单类型不正确")
    if data.quantity <= 0:
        errors.append("数量必须大于 0")
    if data.unit_price <= 0:
        errors.append("单价必须大于 0")
    if data.paid_amount < 0:
        errors.append("已收金额不能小于 0")
    total_amount = max(data.quantity, 0) * max(data.unit_price, 0)
    if total_amount and data.paid_amount > total_amount:
        errors.append("已收金额不能大于总金额")
    return errors


def payment_snapshot(order: Order):
    return {
        "payment_status": normalize_payment_status(order.payment_status),
        "paid_amount": float(order.paid_amount or 0),
        "unpaid_amount": float(order.unpaid_amount or 0),
    }


def delivery_snapshot(order: Order):
    return {
        "delivery_status": normalize_delivery_status(order.delivery_status),
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else "",
    }


def parse_payment_snapshot(value: str):
    try:
        data = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"payment_status": normalize_payment_status(str(value or PAYMENT_UNSETTLED))}
    if not isinstance(data, dict):
        return {"payment_status": PAYMENT_UNSETTLED}
    data["payment_status"] = normalize_payment_status(data.get("payment_status"))
    return data


def get_recent_distinct_values(db: Session, column, keyword: str = "", limit: int = 20):
    query = db.query(
        column.label("value"),
        func.max(Order.created_at).label("last_used_at"),
        func.max(Order.id).label("last_order_id"),
    ).filter(column != None, column != "")
    if keyword:
        query = query.filter(column.like(f"%{keyword}%"))
    rows = query.group_by(column).order_by(
        func.max(Order.created_at).desc(), func.max(Order.id).desc()
    ).limit(limit).all()
    return [row.value for row in rows if row.value]


def get_order_form_options(db: Session):
    return {
        "customer_options": get_recent_distinct_values(db, Order.customer, limit=200),
        "item_options": get_recent_distinct_values(db, Order.item_name, limit=200),
        "size_options": get_recent_distinct_values(db, Order.size, limit=200),
    }


def get_all_order_form_options(db: Session):
    return {
        "customer_options": [row[0] for row in db.query(Order.customer).distinct().order_by(Order.customer.asc()).all() if row[0]],
        "item_options": [row[0] for row in db.query(Order.item_name).distinct().order_by(Order.item_name.asc()).all() if row[0]],
        "size_options": [row[0] for row in db.query(Order.size).distinct().order_by(Order.size.asc()).all() if row[0]],
    }


def get_order_logs(db: Session, order_id: int):
    return (
        db.query(OperationLog)
        .filter(OperationLog.target_type == "order", OperationLog.target_id == order_id)
        .order_by(OperationLog.id.desc())
        .limit(12)
        .all()
    )


def get_dashboard_data(db: Session):
    today = date.today()
    week_start = date.fromordinal(today.toordinal() - today.weekday())
    pending_orders = (
        db.query(Order)
        .filter(or_(Order.payment_status == PAYMENT_UNSETTLED, Order.delivery_status == DELIVERY_WAITING))
        .order_by(
            case(
                ((Order.delivery_status == DELIVERY_DONE) & (Order.payment_status == PAYMENT_UNSETTLED), 0),
                (Order.payment_status == PAYMENT_UNSETTLED, 1),
                else_=2,
            ).asc(),
            Order.order_no.desc(),
        )
        .limit(80)
        .all()
    )
    unpaid_sum = db.query(func.coalesce(func.sum(Order.unpaid_amount), 0)).filter(
        Order.payment_status == PAYMENT_UNSETTLED
    ).scalar() or 0
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    return {
        "pending_orders": pending_orders,
        "today": today,
        "week_start": week_start,
        "dashboard_stats": {
            "unpaid_amount": float(unpaid_sum),
            "unpaid_count": db.query(Order).filter(Order.payment_status == PAYMENT_UNSETTLED).count(),
            "risk_count": db.query(Order).filter(
                Order.delivery_status == DELIVERY_DONE,
                Order.payment_status == PAYMENT_UNSETTLED,
            ).count(),
            "waiting_delivery": db.query(Order).filter(Order.delivery_status == DELIVERY_WAITING).count(),
            "week_count": db.query(Order).filter(Order.created_at >= week_start_dt).count(),
        },
    }


def list_orders(db: Session, filters: OrderListFilters):
    query = db.query(Order)
    if filters.keyword.strip():
        kw = f"%{filters.keyword.strip()}%"
        query = query.filter(or_(
            Order.order_no.like(kw), Order.customer.like(kw), Order.order_type.like(kw),
            Order.item_name.like(kw), Order.size.like(kw), Order.remark.like(kw),
        ))
    if filters.order_type.strip():
        query = query.filter(Order.order_type == normalize_order_type(filters.order_type))
    normalized_payment = normalize_payment_status(filters.payment_status) if filters.payment_status.strip() else ""
    if normalized_payment:
        query = query.filter(Order.payment_status == normalized_payment)
    if filters.delivery_status.strip():
        query = query.filter(Order.delivery_status == normalize_delivery_status(filters.delivery_status))
    if filters.print_status.strip():
        query = query.filter(Order.print_status == filters.print_status.strip())

    parsed_from, from_error = parse_date_field(filters.date_from, "开始日期")
    parsed_to, to_error = parse_date_field(filters.date_to, "结束日期")
    if parsed_from:
        query = query.filter(Order.created_at >= datetime.combine(parsed_from, datetime.min.time()))
    if parsed_to:
        query = query.filter(Order.created_at <= datetime.combine(parsed_to, datetime.max.time()))

    page = max(filters.page, 1)
    per_page = filters.per_page if filters.per_page in [20, 50, 100] else 50
    filtered_query = query
    total_count = filtered_query.count()
    sums = filtered_query.with_entities(
        func.coalesce(func.sum(Order.total_amount), 0),
        func.coalesce(func.sum(Order.unpaid_amount), 0),
    ).one()
    counts = filtered_query.with_entities(
        func.coalesce(func.sum(case((Order.payment_status == PAYMENT_UNSETTLED, 1), else_=0)), 0),
        func.coalesce(func.sum(case(
            ((Order.delivery_status == DELIVERY_DONE) & (Order.payment_status == PAYMENT_UNSETTLED), 1),
            else_=0,
        )), 0),
        func.coalesce(func.sum(case((Order.delivery_status == DELIVERY_WAITING, 1), else_=0)), 0),
        func.coalesce(func.sum(case((Order.print_status == "未打印", 1), else_=0)), 0),
    ).one()

    if filters.sort_by == "risk_first":
        risk_order = case(
            ((Order.delivery_status == DELIVERY_DONE) & (Order.payment_status == PAYMENT_UNSETTLED), 0),
            (Order.payment_status == PAYMENT_UNSETTLED, 1),
            (Order.delivery_status == DELIVERY_WAITING, 2),
            else_=3,
        )
        query = query.order_by(risk_order.asc(), Order.unpaid_amount.desc(), Order.order_no.desc())
    elif filters.sort_by == "payment_first":
        query = query.order_by(case((Order.payment_status == PAYMENT_UNSETTLED, 0), else_=2).asc(), Order.order_no.desc())
    elif filters.sort_by == "order_new":
        query = query.order_by(Order.order_no.desc())
    elif filters.sort_by == "order_old":
        query = query.order_by(Order.order_no.asc())
    elif filters.sort_by == "customer":
        query = query.order_by(Order.customer.asc(), Order.order_no.desc())
    elif filters.sort_by == "item":
        query = query.order_by(Order.item_name.asc(), Order.order_no.desc())
    elif filters.sort_by == "amount_desc":
        query = query.order_by(Order.total_amount.desc(), Order.order_no.desc())
    elif filters.sort_by == "amount_asc":
        query = query.order_by(Order.total_amount.asc(), Order.order_no.desc())
    elif filters.sort_by == "unpaid_desc":
        query = query.order_by(Order.unpaid_amount.desc(), Order.order_no.desc())
    else:
        query = query.order_by(Order.order_no.desc())

    page_count = max((total_count + per_page - 1) // per_page, 1)
    page = min(page, page_count)
    return {
        "orders": query.offset((page - 1) * per_page).limit(per_page).all(),
        "normalized_payment": normalized_payment,
        "date_from": filters.date_from if not from_error else "",
        "date_to": filters.date_to if not to_error else "",
        "date_errors": [item for item in [from_error, to_error] if item],
        "total_amount_sum": float(sums[0] or 0),
        "balance_due_sum": float(sums[1] or 0),
        "filtered_unpaid_count": int(counts[0] or 0),
        "filtered_risk_count": int(counts[1] or 0),
        "filtered_waiting_delivery_count": int(counts[2] or 0),
        "filtered_unprinted_count": int(counts[3] or 0),
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "page_count": page_count,
    }


def get_recent_price(db: Session, item_name: str, size: str = ""):
    if not item_name.strip():
        return None
    query = db.query(Order).filter(Order.item_name == item_name.strip())
    if size.strip():
        query = query.filter(Order.size == size.strip())
    return query.order_by(Order.created_at.desc(), Order.id.desc()).first()


def create_order(db: Session, data: OrderFormData):
    errors = validate_order_form(data)
    if errors:
        return None, errors
    order_type = normalize_order_type(data.order_type)
    total_amount = data.quantity * data.unit_price
    unpaid_amount, payment_status = calc_payment_status(total_amount, data.paid_amount)
    order = Order(
        order_no=generate_order_no(db), customer=data.customer, phone=data.phone,
        order_type=order_type, item_name=data.item_name, size=data.size,
        quantity=data.quantity, unit_price=data.unit_price, total_amount=total_amount,
        paid_amount=data.paid_amount, unpaid_amount=unpaid_amount,
        payment_status=payment_status, print_status="未打印", delivery_status=DELIVERY_WAITING,
        priority_color="灰色", due_date=None, remark=data.remark,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order, []


def update_order(db: Session, order: Order, data: OrderFormData, operator: str):
    errors = validate_order_form(data)
    if errors:
        return errors
    order_type = normalize_order_type(data.order_type)
    total_amount = data.quantity * data.unit_price
    unpaid_amount, payment_status = calc_payment_status(total_amount, data.paid_amount, order.payment_status)
    order.customer = data.customer
    order.phone = data.phone
    order.order_type = order_type
    order.item_name = data.item_name
    order.size = data.size
    order.quantity = data.quantity
    order.unit_price = data.unit_price
    order.total_amount = total_amount
    order.paid_amount = data.paid_amount
    order.unpaid_amount = unpaid_amount
    order.payment_status = payment_status
    order.remark = data.remark
    log_operation(
        db, "order", order.id, "edit_order", "multiple", "订单被编辑",
        f"customer={data.customer}, order_type={order_type}, item_name={data.item_name}, size={data.size}, quantity={data.quantity}, unit_price={data.unit_price}, paid_amount={data.paid_amount}",
        operator,
    )
    db.commit()
    return []


def mark_paid(db: Session, order: Order, operator: str):
    old_value = json.dumps(payment_snapshot(order), ensure_ascii=False)
    order.payment_status = PAYMENT_SETTLED
    order.paid_amount = float(order.total_amount or 0)
    order.unpaid_amount = 0.0
    log_operation(db, "order", order.id, "mark_paid", "payment_status", old_value,
                  json.dumps(payment_snapshot(order), ensure_ascii=False), operator)
    db.commit()


def record_payment(db: Session, order: Order, amount, operator: str) -> str:
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        return "请输入正确的本次收款金额"
    if not math.isfinite(amount) or amount <= 0:
        return "本次收款金额必须大于 0"

    total_amount = round(float(order.total_amount or 0), 2)
    paid_amount = round(max(float(order.paid_amount or 0), 0), 2)
    balance_due = round(max(total_amount - paid_amount, 0), 2)
    if normalize_payment_status(order.payment_status) == PAYMENT_SETTLED or balance_due <= 0:
        return "该订单已经结清，无需再次收款"
    if amount > balance_due:
        return f"本次收款不能大于当前欠款 {balance_due:.2f}"

    old_value = json.dumps(payment_snapshot(order), ensure_ascii=False)
    order.paid_amount = round(paid_amount + amount, 2)
    order.unpaid_amount = round(max(total_amount - order.paid_amount, 0), 2)
    order.payment_status = PAYMENT_SETTLED if order.unpaid_amount <= 0 else PAYMENT_UNSETTLED
    log_operation(
        db, "order", order.id, "record_payment", "payment_status", old_value,
        json.dumps(payment_snapshot(order), ensure_ascii=False), operator,
    )
    db.commit()
    return ""


def mark_unpaid(db: Session, order: Order, operator: str):
    old_value = json.dumps(payment_snapshot(order), ensure_ascii=False)
    order.payment_status = PAYMENT_UNSETTLED
    order.unpaid_amount = max(float(order.total_amount or 0) - float(order.paid_amount or 0), 0.0)
    if order.unpaid_amount <= 0:
        order.paid_amount = 0.0
        order.unpaid_amount = float(order.total_amount or 0)
    log_operation(db, "order", order.id, "mark_unpaid", "payment_status", old_value,
                  json.dumps(payment_snapshot(order), ensure_ascii=False), operator)
    db.commit()


def mark_delivered(db: Session, order: Order, operator: str) -> bool:
    if normalize_delivery_status(order.delivery_status) == DELIVERY_DONE:
        return False
    old_value = json.dumps(delivery_snapshot(order), ensure_ascii=False)
    order.delivery_status = DELIVERY_DONE
    order.delivered_at = datetime.utcnow()
    log_operation(
        db, "order", order.id, "mark_delivered", "delivery_status", old_value,
        json.dumps(delivery_snapshot(order), ensure_ascii=False), operator,
    )
    db.commit()
    return True


def delete_order(db: Session, order: Order, operator: str):
    order_no = order.order_no
    log_operation(db, "order", order.id, "delete_order", "order", f"order_no={order_no}", "deleted", operator)
    db.delete(order)
    db.commit()
    return order_no


def undo_last_action(db: Session, order: Order, operator: str, apply_print_snapshot):
    log = get_latest_reversible_log(db, order.id)
    if log is None:
        return None
    if log.field_name == "print_status":
        current_value = json.dumps({
            "print_status": order.print_status,
            "delivery_status": normalize_delivery_status(order.delivery_status),
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else "",
        }, ensure_ascii=False)
        try:
            old_snapshot = json.loads(log.old_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            old_snapshot = {"print_status": log.old_value, "delivery_status": DELIVERY_WAITING}
        apply_print_snapshot(order, old_snapshot)
        new_value = json.dumps({
            "print_status": order.print_status,
            "delivery_status": order.delivery_status,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else "",
        }, ensure_ascii=False)
        log_operation(db, "order", order.id, "undo_print_status", "print_status", current_value, new_value, operator)
    elif log.field_name == "payment_status":
        current_value = order.payment_status
        old_snapshot = parse_payment_snapshot(log.old_value)
        order.payment_status = old_snapshot.get("payment_status") or PAYMENT_UNSETTLED
        if "paid_amount" in old_snapshot:
            order.paid_amount = float(old_snapshot.get("paid_amount") or 0)
            order.unpaid_amount = float(old_snapshot.get("unpaid_amount") or 0)
        elif order.payment_status == PAYMENT_SETTLED:
            order.paid_amount = float(order.total_amount or 0)
            order.unpaid_amount = 0.0
        else:
            order.unpaid_amount, order.payment_status = calc_payment_status(
                order.total_amount, order.paid_amount, PAYMENT_UNSETTLED
            )
        log_operation(db, "order", order.id, "undo_payment_status", "payment_status", current_value, order.payment_status, operator)
    elif log.field_name == "delivery_status":
        current_value = json.dumps(delivery_snapshot(order), ensure_ascii=False)
        try:
            old_snapshot = json.loads(log.old_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            old_snapshot = {"delivery_status": DELIVERY_WAITING, "delivered_at": ""}
        order.delivery_status = normalize_delivery_status(old_snapshot.get("delivery_status"))
        delivered_at = old_snapshot.get("delivered_at") or ""
        try:
            order.delivered_at = datetime.fromisoformat(delivered_at) if delivered_at else None
        except ValueError:
            order.delivered_at = None
        log_operation(
            db, "order", order.id, "undo_delivery_status", "delivery_status",
            current_value, json.dumps(delivery_snapshot(order), ensure_ascii=False), operator,
        )
    db.commit()
    return log
