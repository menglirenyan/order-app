import json
import re
from datetime import date
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import Order
from .orders import (
    DELIVERY_DONE,
    DELIVERY_WAITING,
    ORDER_TYPES,
    PAYMENT_SETTLED,
    PAYMENT_UNSETTLED,
    normalize_order_type,
    normalize_payment_status,
)

ORDER_DRAFT_FIELDS = {
    "customer", "phone", "order_type", "item_name", "size",
    "quantity", "unit_price", "paid_amount", "remark",
}


def normalize_order_draft(raw: dict):
    draft = {field: raw.get(field, "") for field in ORDER_DRAFT_FIELDS}
    issues = []
    for field in ["customer", "phone", "item_name", "size", "remark"]:
        draft[field] = str(draft.get(field) or "").strip()
    draft["order_type"] = normalize_order_type(draft.get("order_type"))
    try:
        draft["quantity"] = int(draft.get("quantity") or 0)
    except (TypeError, ValueError):
        draft["quantity"] = 0
    if draft["quantity"] <= 0:
        issues.append("数量缺失或不合法")
    for field in ["unit_price", "paid_amount"]:
        try:
            draft[field] = float(draft.get(field) or 0)
        except (TypeError, ValueError):
            draft[field] = 0.0
    if draft["unit_price"] <= 0:
        issues.append("单价缺失或不合法")
    if draft["paid_amount"] < 0:
        draft["paid_amount"] = 0.0
    if not draft["customer"]:
        issues.append("客户名称缺失")
    if not draft["item_name"]:
        issues.append("商品名称缺失")
    return draft, issues


def build_order_hotwords(db: Session):
    customers = [row[0] for row in db.query(Order.customer).distinct().order_by(Order.customer.asc()).limit(60).all() if row[0]]
    items = [row[0] for row in db.query(Order.item_name).distinct().order_by(Order.item_name.asc()).limit(80).all() if row[0]]
    sizes = [row[0] for row in db.query(Order.size).distinct().order_by(Order.size.asc()).limit(80).all() if row[0]]
    return {"customers": customers, "items": items, "sizes": sizes}


def apply_hotwords_to_draft(text_value: str, draft: dict, hotwords: dict | None):
    if not hotwords:
        return draft
    for field, values in [
        ("customer", hotwords.get("customers", [])),
        ("item_name", hotwords.get("items", [])),
        ("size", hotwords.get("sizes", [])),
    ]:
        if not draft.get(field):
            matches = [value for value in values if value and value in text_value]
            if matches:
                draft[field] = max(matches, key=len)
    return draft


def fill_recent_unit_price(db: Session, draft: dict):
    if draft.get("unit_price", 0) > 0 or not draft.get("item_name"):
        return draft
    query = db.query(Order).filter(Order.item_name == draft["item_name"])
    if draft.get("size"):
        query = query.filter(Order.size == draft["size"])
    recent_order = query.order_by(Order.created_at.desc(), Order.id.desc()).first()
    if recent_order and recent_order.unit_price:
        draft["unit_price"] = recent_order.unit_price
    return draft


def normalize_order_result(raw: dict, text_value: str, db: Session, hotwords: dict | None):
    raw_orders = raw.get("orders") if isinstance(raw.get("orders"), list) else None
    source_issues = raw.get("issues") if isinstance(raw.get("issues"), list) else []
    confidence = raw.get("confidence", 0.7)
    if not raw_orders:
        raw_orders = [raw]
    orders = []
    all_issues = [str(issue) for issue in source_issues if issue]
    for index, raw_order in enumerate(raw_orders, start=1):
        if not isinstance(raw_order, dict):
            all_issues.append(f"第 {index} 个订单结构不合法")
            continue
        draft, _ = normalize_order_draft(raw_order)
        draft = apply_hotwords_to_draft(text_value, draft, hotwords)
        draft = fill_recent_unit_price(db, draft)
        draft, issues = normalize_order_draft(draft)
        orders.append({"draft": draft, "issues": issues})
        all_issues.extend([f"订单 {index}：{issue}" for issue in issues])
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.7
    return {"orders": orders, "issues": all_issues, "confidence": max(0, min(confidence, 1))}


def heuristic_order_draft(text_value: str, hotwords: dict | None = None):
    text_value = text_value.strip()
    draft = {
        "customer": "", "phone": "", "order_type": "瓦楞板", "item_name": "",
        "size": "", "quantity": 1, "unit_price": 0, "paid_amount": 0, "remark": text_value,
    }
    for order_type in ORDER_TYPES:
        if order_type in text_value:
            draft["order_type"] = order_type
            break
    patterns = {
        "phone": r"1[3-9]\d{9}",
        "quantity": r"(\d+)\s*(?:个|件|套|张|米|份|只|台|本)?",
        "unit_price": r"(?:单价|每个|每件|价格)\s*(\d+(?:\.\d+)?)",
        "paid_amount": r"(?:定金|已付|付了)\s*(\d+(?:\.\d+)?)",
        "customer": r"(?:客户|给|帮)\s*([\u4e00-\u9fa5A-Za-z0-9_-]{2,12})",
        "item_name": r"(?:做|要|下单|订)\s*([\u4e00-\u9fa5A-Za-z0-9_ xX*.-]{2,30})",
        "size": r"(\d+(?:\.\d+)?\s*[xX*]\s*\d+(?:\.\d+)?(?:\s*[xX*]\s*\d+(?:\.\d+)?)?)",
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, text_value)
        if not match:
            continue
        value = match.group(0) if field == "phone" else match.group(1)
        if field == "quantity":
            value = int(value)
        elif field in ["unit_price", "paid_amount"]:
            value = float(value)
        elif field == "item_name":
            value = value.strip(" ，,。")
        elif field == "size":
            value = value.replace(" ", "")
        draft[field] = value
    draft = apply_hotwords_to_draft(text_value, draft, hotwords)
    return normalize_order_draft(draft)


def extract_json_object(content: str):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _call_deepseek(model: str, user_text: str, system_prompt: str, empty_message: str):
    if not settings.deepseek_api_key:
        return None, "未配置 DEEPSEEK_API_KEY，已使用本地规则生成" + ("查询条件" if "查询" in empty_message else "草稿")
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
    }
    req = urlrequest.Request(
        settings.deepseek_base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {settings.deepseek_api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"DeepSeek 调用失败：{exc}"
    content = data["choices"][0]["message"].get("content") or ""
    if not content.strip():
        return None, empty_message
    return extract_json_object(content), ""


def call_deepseek_model(model: str, user_text: str, hotwords: dict | None = None):
    prompt = (
        "你是订单录入助手。把自然语言解析为 JSON，只返回合法 JSON。顶层必须有 orders, issues, confidence。"
        "每个订单必须有 customer, phone, order_type, item_name, size, quantity, unit_price, paid_amount, remark。"
        "order_type 只能是瓦楞板或激光切割；无法判断填瓦楞板；无法确定的字段使用空字符串或 0。"
        f"历史热词 JSON：{json.dumps(hotwords or {}, ensure_ascii=False)}。接近历史热词时使用标准写法。"
    )
    return _call_deepseek(model, user_text, prompt, "DeepSeek 返回了空 JSON 内容，请重试或补充订单描述")


def call_deepseek_query_model(model: str, user_text: str, hotwords: dict | None = None):
    prompt = (
        "你是订单查询助手。把自然语言解析为 JSON，只返回合法 JSON。字段必须有 keyword, order_type, payment_status, "
        "delivery_status, print_status, date_from, date_to, sort_by, issues, confidence。日期使用 YYYY-MM-DD。"
        "sort_by 只能是 risk_first/payment_first/order_new/order_old/customer/item/amount_desc/amount_asc/unpaid_desc。"
        f"今天日期：{date.today().isoformat()}。历史热词 JSON：{json.dumps(hotwords or {}, ensure_ascii=False)}。"
    )
    return _call_deepseek(model, user_text, prompt, "DeepSeek 返回了空 JSON 内容，请重试或补充查询描述")


def month_range(base_date: date, offset: int = 0):
    month_index = base_date.month - 1 + offset
    year, month = base_date.year + month_index // 12, month_index % 12 + 1
    start = date(year, month, 1)
    next_index = month_index + 1
    next_start = date(base_date.year + next_index // 12, next_index % 12 + 1, 1)
    return start.isoformat(), date.fromordinal(next_start.toordinal() - 1).isoformat()


def normalize_order_query(raw: dict):
    allowed_sort = ["risk_first", "payment_first", "order_new", "order_old", "customer", "item", "amount_desc", "amount_asc", "unpaid_desc"]
    draft = {
        "keyword": str(raw.get("keyword") or "").strip(),
        "order_type": str(raw.get("order_type") or "").strip(),
        "payment_status": normalize_payment_status(raw.get("payment_status")) if str(raw.get("payment_status") or "").strip() else "",
        "delivery_status": str(raw.get("delivery_status") or "").strip(),
        "print_status": str(raw.get("print_status") or "").strip(),
        "date_from": str(raw.get("date_from") or "").strip(),
        "date_to": str(raw.get("date_to") or "").strip(),
        "sort_by": str(raw.get("sort_by") or "risk_first").strip(),
    }
    issues = [str(issue) for issue in raw.get("issues", []) if issue] if isinstance(raw.get("issues"), list) else []
    if draft["order_type"] and draft["order_type"] not in ORDER_TYPES:
        issues.append("订单类型不明确")
        draft["order_type"] = ""
    for field, allowed, message in [
        ("payment_status", ["", PAYMENT_UNSETTLED, PAYMENT_SETTLED], "付款状态不明确"),
        ("delivery_status", ["", DELIVERY_WAITING, DELIVERY_DONE], "拉走状态不明确"),
        ("print_status", ["", "未打印", "已打印"], "打印状态不明确"),
    ]:
        if draft[field] not in allowed:
            issues.append(message)
            draft[field] = ""
    if draft["sort_by"] not in allowed_sort:
        draft["sort_by"] = "risk_first"
    for field in ["date_from", "date_to"]:
        if draft[field]:
            try:
                date.fromisoformat(draft[field])
            except ValueError:
                issues.append(f"{field} 日期格式不正确")
                draft[field] = ""
    try:
        confidence = float(raw.get("confidence", 0.7))
    except (TypeError, ValueError):
        confidence = 0.7
    return draft, issues, max(0, min(confidence, 1))


def heuristic_order_query(text_value: str, hotwords: dict | None = None):
    today = date.today()
    draft = {field: "" for field in ["keyword", "order_type", "payment_status", "delivery_status", "print_status", "date_from", "date_to"]}
    draft["sort_by"] = "risk_first"
    for order_type in ORDER_TYPES:
        if order_type in text_value:
            draft["order_type"] = order_type
            break
    if any(word in text_value for word in ["未付", "欠款", "没结清"]):
        draft["payment_status"] = PAYMENT_UNSETTLED
    elif any(word in text_value for word in ["已结清", "结清", "已付款"]):
        draft["payment_status"] = PAYMENT_SETTLED
    for status in [PAYMENT_UNSETTLED, PAYMENT_SETTLED]:
        if status in text_value:
            draft["payment_status"] = status
            break
    for status in [DELIVERY_WAITING, DELIVERY_DONE]:
        if status in text_value:
            draft["delivery_status"] = status
            break
    for status in ["未打印", "已打印"]:
        if status in text_value:
            draft["print_status"] = status
            break
    if "今天" in text_value:
        draft["date_from"] = draft["date_to"] = today.isoformat()
    elif "本月" in text_value or "这个月" in text_value:
        draft["date_from"], draft["date_to"] = month_range(today)
    elif "上月" in text_value or "上个月" in text_value:
        draft["date_from"], draft["date_to"] = month_range(today, -1)
    elif "今年" in text_value or "本年" in text_value:
        draft["date_from"], draft["date_to"] = date(today.year, 1, 1).isoformat(), date(today.year, 12, 31).isoformat()
    if ("未付" in text_value or "待结" in text_value) and ("高" in text_value or "多" in text_value):
        draft["sort_by"] = "unpaid_desc"
    elif "金额高" in text_value or "总额高" in text_value:
        draft["sort_by"] = "amount_desc"
    elif "金额低" in text_value or "总额低" in text_value:
        draft["sort_by"] = "amount_asc"
    elif "新" in text_value:
        draft["sort_by"] = "order_new"
    elif "旧" in text_value:
        draft["sort_by"] = "order_old"
    if hotwords:
        values = hotwords.get("customers", []) + hotwords.get("items", []) + hotwords.get("sizes", [])
        matches = [value for value in values if value and value in text_value]
        if matches:
            draft["keyword"] = max(matches, key=len)
    if not draft["keyword"]:
        match = re.search(r"(?:查|查询|搜索|找|看看)\s*([\u4e00-\u9fa5A-Za-z0-9_*xX.-]{2,20})", text_value)
        if match:
            draft["keyword"] = match.group(1).strip(" 的订单")
    return normalize_order_query({**draft, "issues": [], "confidence": 0.45})


def parse_voice_order(db: Session, text_value: str):
    hotwords = build_order_hotwords(db)
    raw, message = call_deepseek_model(settings.deepseek_flash_model, text_value, hotwords)
    source_model = settings.deepseek_flash_model
    if raw is None:
        draft, issues = heuristic_order_draft(text_value, hotwords)
        draft = fill_recent_unit_price(db, draft)
        draft, issues = normalize_order_draft(draft)
        result = {"orders": [{"draft": draft, "issues": issues}], "issues": issues[:], "confidence": 0.45}
        source_model = "local-rules"
        if message:
            result["issues"].append(message)
    else:
        result = normalize_order_result(raw, text_value, db, hotwords)
    conflict_words = ["两个订单", "多个订单", "分别", "另外", "再来一单", "还有一单"]
    needs_pro = len(result["orders"]) > 1 or len(result["issues"]) >= 2 or any(word in text_value for word in conflict_words) or result["confidence"] < 0.65
    if needs_pro and source_model != "local-rules":
        pro_raw, pro_message = call_deepseek_model(settings.deepseek_pro_model, text_value, hotwords)
        if pro_raw is not None:
            result = normalize_order_result(pro_raw, text_value, db, hotwords)
            source_model = settings.deepseek_pro_model
        elif pro_message:
            result["issues"].append(pro_message)
    first_draft = result["orders"][0]["draft"] if result["orders"] else {}
    return {
        "ok": True, "draft": first_draft, "orders": result["orders"], "issues": result["issues"],
        "confidence": result["confidence"], "source_model": source_model,
        "needs_review": bool(result["issues"]) or len(result["orders"]) > 1, "hotwords": hotwords,
    }


def parse_voice_query(db: Session, text_value: str):
    hotwords = build_order_hotwords(db)
    raw, message = call_deepseek_query_model(settings.deepseek_flash_model, text_value, hotwords)
    source_model = settings.deepseek_flash_model
    if raw is None:
        draft, issues, confidence = heuristic_order_query(text_value, hotwords)
        source_model = "local-rules"
        if message:
            issues.append(message)
    else:
        draft, issues, confidence = normalize_order_query(raw)
    if confidence < 0.65 or issues:
        pro_raw, pro_message = call_deepseek_query_model(settings.deepseek_pro_model, text_value, hotwords)
        if pro_raw is not None:
            draft, issues, confidence = normalize_order_query(pro_raw)
            source_model = settings.deepseek_pro_model
        elif pro_message:
            issues.append(pro_message)
    return {
        "ok": True, "draft": draft, "issues": issues, "confidence": confidence,
        "source_model": source_model, "needs_review": True,
    }
