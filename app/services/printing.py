import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import AppSetting, Order
from .audit import log_operation
from .orders import DELIVERY_DONE, normalize_delivery_status

DELIVERY_PRINT_CONFIG_KEY = "delivery_print_config"
DELIVERY_PRINT_CONFIG_DEFAULT = {
    "title": "方圆五金出货单",
    "copies": ["客户联", "财务联", "存根联"],
    "unit": "件",
    "footer_lines": [
        "本厂大型激光切割，剪板，折叠对外加工，专业定尺生产瓦楞板，波浪板，三角板，不锈钢板，黑钛瓦楞，三角，波浪板均可",
        "定尺生产！可提供火锅桌架全套配件！",
        "门市地址：东段君良仓储西800米路北  厂址：东段速8酒店后面50米道东",
        "电话：15226662348    13582962755（微信同步）",
    ],
    "delivery_person_label": "送货人",
    "delivery_person_value": "",
    "receiver_sign_label": "收货人签字",
}


def build_delivery_print_order_data(order: Order) -> dict:
    return {
        "id": order.id,
        "order_no": order.order_no,
        "created_date": order.created_at.strftime("%Y-%m-%d") if order.created_at else "",
        "customer": order.customer or "",
        "phone": order.phone or "",
        "item_name": order.item_name or "",
        "size": order.size or "",
        "quantity": order.quantity or "",
        "unit_price": float(order.unit_price or 0),
        "total_amount": float(order.total_amount or 0),
        "remark": order.remark or "",
    }


def get_app_setting(db: Session, key: str, default: str = "") -> str:
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    return default if setting is None else str(setting.value or default)


def set_app_setting(db: Session, key: str, value: str):
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    if setting is None:
        setting = AppSetting(key=key, value=value, updated_at=datetime.utcnow())
        db.add(setting)
    else:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    return setting


def split_lines(value: str) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def normalize_delivery_print_config(value) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            value = {}
    if not isinstance(value, dict):
        value = {}
    config = dict(DELIVERY_PRINT_CONFIG_DEFAULT)
    config.update({key: value.get(key) for key in DELIVERY_PRINT_CONFIG_DEFAULT if value.get(key) is not None})
    copies = config.get("copies")
    if isinstance(copies, str):
        copies = split_lines(copies)
    if not isinstance(copies, list):
        copies = []
    copies = [str(item or "").strip() for item in copies if str(item or "").strip()]
    copies = copies[:3] if len(copies) >= 3 else list(DELIVERY_PRINT_CONFIG_DEFAULT["copies"])
    footer_lines = config.get("footer_lines")
    if isinstance(footer_lines, str):
        footer_lines = split_lines(footer_lines)
    if not isinstance(footer_lines, list):
        footer_lines = []
    footer_lines = [str(item or "").strip() for item in footer_lines if str(item or "").strip()]
    return {
        "title": str(config.get("title") or "").strip() or DELIVERY_PRINT_CONFIG_DEFAULT["title"],
        "copies": copies,
        "unit": str(config.get("unit") or "").strip() or DELIVERY_PRINT_CONFIG_DEFAULT["unit"],
        "footer_lines": footer_lines or list(DELIVERY_PRINT_CONFIG_DEFAULT["footer_lines"]),
        "delivery_person_label": str(config.get("delivery_person_label") or "").strip() or DELIVERY_PRINT_CONFIG_DEFAULT["delivery_person_label"],
        "delivery_person_value": str(config.get("delivery_person_value") or "").strip(),
        "receiver_sign_label": str(config.get("receiver_sign_label") or "").strip() or DELIVERY_PRINT_CONFIG_DEFAULT["receiver_sign_label"],
    }


def get_delivery_print_config(db: Session) -> dict:
    return normalize_delivery_print_config(get_app_setting(db, DELIVERY_PRINT_CONFIG_KEY, "{}"))


def set_delivery_print_config(db: Session, config: dict) -> None:
    set_app_setting(db, DELIVERY_PRINT_CONFIG_KEY, json.dumps(normalize_delivery_print_config(config), ensure_ascii=False))
    db.commit()


def print_delivery_snapshot(order: Order):
    return {
        "print_status": order.print_status,
        "delivery_status": normalize_delivery_status(order.delivery_status),
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else "",
    }


def apply_print_delivery_snapshot(order: Order, snapshot: dict) -> None:
    order.print_status = snapshot.get("print_status") or "未打印"
    order.delivery_status = normalize_delivery_status(snapshot.get("delivery_status"))
    delivered_at = snapshot.get("delivered_at") or ""
    if delivered_at:
        try:
            order.delivered_at = datetime.fromisoformat(delivered_at)
        except ValueError:
            order.delivered_at = None
    else:
        order.delivered_at = None


def mark_orders_printed(db: Session, orders: list[Order], operator: str = ""):
    printed = []
    skipped = []
    for order in orders:
        if order.print_status == "已打印" and normalize_delivery_status(order.delivery_status) == DELIVERY_DONE:
            skipped.append(order)
            continue
        old_value = json.dumps(print_delivery_snapshot(order), ensure_ascii=False)
        order.print_status = "已打印"
        order.delivery_status = DELIVERY_DONE
        order.delivered_at = datetime.utcnow()
        log_operation(
            db, "order", order.id, "mark_printed", "print_status", old_value,
            json.dumps(print_delivery_snapshot(order), ensure_ascii=False), operator,
        )
        printed.append(order)
    db.commit()
    return printed, skipped


def prepare_print_job(db: Session, orders: list[Order], operator: str):
    printed, skipped = mark_orders_printed(db, orders, operator)
    return {
        "printed": printed,
        "skipped": skipped,
        "orders": [build_delivery_print_order_data(order) for order in printed],
        "print_config": get_delivery_print_config(db),
    }
