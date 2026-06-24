from io import BytesIO

from PIL import Image
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AppSetting, OperationLog, Order, ShowcaseItem, User
from tests.conftest import login


def order_payload(**overrides):
    payload = {
        "customer": "测试客户", "phone": "13800000000", "order_type": "瓦楞板",
        "item_name": "测试商品", "size": "30x40", "quantity": "2",
        "unit_price": "80", "paid_amount": "50", "remark": "测试备注",
    }
    payload.update(overrides)
    return payload


def get_order():
    db = SessionLocal()
    try:
        return db.query(Order).order_by(Order.id.desc()).first()
    finally:
        db.close()


def test_private_pages_redirect_to_login(client):
    for path in ["/dashboard", "/orders", "/orders/new", "/showcase/manage", "/users"]:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] in ["/login", "/orders"]


def test_login_and_order_crud_status_workflow(client, admin_user):
    response = login(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    invalid = client.post("/orders", data=order_payload(quantity="0"))
    assert invalid.status_code == 400
    assert "数量必须大于 0" in invalid.text

    created = client.post("/orders", data=order_payload(), follow_redirects=False)
    assert created.status_code == 303
    order = get_order()
    assert order.order_no.endswith("-001")
    assert order.total_amount == 160
    assert order.unpaid_amount == 110
    assert order.payment_status == "未结清"

    listing = client.get("/orders?keyword=测试客户&payment_status=未结清")
    assert listing.status_code == 200
    assert "测试客户" in listing.text
    assert "欠款 110.00" in listing.text or "110.00" in listing.text

    edited = client.post(
        f"/orders/{order.id}/edit",
        data=order_payload(quantity="3", unit_price="90", paid_amount="70"),
        follow_redirects=False,
    )
    assert edited.status_code == 303
    order = get_order()
    assert order.total_amount == 270
    assert order.unpaid_amount == 200

    dashboard = client.get("/dashboard")
    detail = client.get(f"/orders/{order.id}")
    for response in [dashboard, detail]:
        assert f'/orders/{order.id}/delivered' in response.text
        assert f'/orders/{order.id}/payment' in response.text

    partial_payment = client.post(
        f"/orders/{order.id}/payment",
        data={"amount": "80", "return_to": f"/orders/{order.id}"},
        follow_redirects=False,
    )
    assert partial_payment.status_code == 303
    order = get_order()
    assert order.paid_amount == 150
    assert order.unpaid_amount == 120
    assert order.payment_status == "未结清"

    overpayment = client.post(
        f"/orders/{order.id}/payment",
        data={"amount": "121", "return_to": f"/orders/{order.id}"},
        follow_redirects=False,
    )
    assert overpayment.status_code == 303
    order = get_order()
    assert order.paid_amount == 150
    assert order.unpaid_amount == 120

    undone_payment = client.post(f"/orders/{order.id}/undo", follow_redirects=False)
    assert undone_payment.status_code == 303
    order = get_order()
    assert order.paid_amount == 70
    assert order.unpaid_amount == 200

    delivered = client.post(
        f"/orders/{order.id}/delivered",
        data={"return_to": f"/orders/{order.id}"},
        follow_redirects=False,
    )
    assert delivered.status_code == 303
    order = get_order()
    assert order.delivery_status == "已拉走"
    assert order.print_status == "未打印"

    undone_delivery = client.post(f"/orders/{order.id}/undo", follow_redirects=False)
    assert undone_delivery.status_code == 303
    order = get_order()
    assert order.delivery_status == "未拉走"
    assert order.print_status == "未打印"

    paid = client.post(f"/orders/{order.id}/paid", data={}, follow_redirects=False)
    assert paid.status_code == 303
    order = get_order()
    assert order.payment_status == "已结清"
    assert order.paid_amount == order.total_amount

    undone = client.post(f"/orders/{order.id}/undo", follow_redirects=False)
    assert undone.status_code == 303
    order = get_order()
    assert order.payment_status == "未结清"
    assert order.paid_amount == 70

    printed = client.post(f"/orders/{order.id}/print", data={}, follow_redirects=False)
    assert printed.status_code == 200
    assert "方圆五金出货单" in printed.text
    assert printed.text.count('<article class="delivery-copy">') == 1
    assert "客户联" not in printed.text
    assert "财务联" not in printed.text
    assert "存根联" not in printed.text
    order = get_order()
    assert order.print_status == "已打印"
    assert order.delivery_status == "已拉走"

    client.post(f"/orders/{order.id}/undo", follow_redirects=False)
    order = get_order()
    assert order.print_status == "未打印"
    assert order.delivery_status == "未拉走"

    deleted = client.post(f"/orders/{order.id}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert get_order() is None


def test_batch_print_and_print_settings(client, admin_user):
    login(client)
    settings_page = client.get("/print-settings")
    assert settings_page.status_code == 200
    assert "三层复写纸只打印一次" in settings_page.text
    assert "三联名称" not in settings_page.text
    for customer in ["甲", "乙"]:
        client.post("/orders", data=order_payload(customer=customer))
    db = SessionLocal()
    try:
        ids = [row.id for row in db.query(Order).order_by(Order.id).all()]
    finally:
        db.close()
    response = client.post(
        "/orders/batch-print",
        data={"order_ids": [str(item) for item in ids], "return_to": "/orders"},
    )
    assert response.status_code == 200
    assert response.text.count("方圆五金出货单") == len(ids)
    assert response.text.count('<article class="delivery-copy">') == len(ids)

    saved = client.post(
        "/print-settings/delivery-config",
        data={
            "title": "测试出货单", "copies_text": "客户联\n财务联\n存根联", "unit": "件",
            "footer_lines_text": "第一行", "delivery_person_label": "送货人",
            "delivery_person_value": "张三", "receiver_sign_label": "签收",
        }, follow_redirects=False,
    )
    assert saved.status_code == 303
    db = SessionLocal()
    try:
        assert db.query(AppSetting).filter(AppSetting.key == "delivery_print_config").first() is not None
    finally:
        db.close()


def test_voice_endpoints_use_local_fallback(client, admin_user):
    login(client)
    draft = client.post("/api/voice-order-draft", json={"text": "给张三做门头2件单价80定金50"})
    assert draft.status_code == 200
    assert draft.json()["ok"] is True
    assert draft.json()["source_model"] == "local-rules"
    query = client.post("/api/voice-order-query-draft", json={"text": "查本月未结清订单"})
    assert query.status_code == 200
    assert query.json()["draft"]["payment_status"] == "未结清"


def test_showcase_create_public_delete_and_exports(client, admin_user):
    login(client)
    image = Image.new("RGB", (20, 20), "red")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = client.post(
        "/showcase/manage/new",
        data={"title": "样品", "category": "板材", "description": "说明", "is_visible": "true"},
        files={"image_file": ("sample.png", buffer.getvalue(), "image/png")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    public = client.get("/showcase?q=样品")
    assert public.status_code == 200
    assert "样品" in public.text
    db = SessionLocal()
    try:
        item = db.query(ShowcaseItem).one()
        item_id, image_url = item.id, item.image_url
    finally:
        db.close()
    rows = [{"name": "样品", "image_url": image_url, "size": "20x20", "quantity": "2", "price": "5"}]
    assert client.post("/showcase/quotation/image", json={"rows": rows}).headers["content-type"] == "image/png"
    excel = client.post("/showcase/quotation/excel", json={"rows": rows})
    assert "spreadsheetml" in excel.headers["content-type"]
    deleted = client.post("/showcase/manage/delete", json={"ids": [item_id]})
    assert deleted.json() == {"ok": True, "deleted": 1}


def test_admin_user_management_and_permissions(client, admin_user, normal_user):
    login(client, "worker")
    denied = client.get("/users", follow_redirects=False)
    assert denied.status_code == 303
    assert denied.headers["location"] == "/orders"
    client.get("/logout")
    login(client)
    created = client.post(
        "/users/new",
        data={"username": "new-user", "password": "abc123", "confirm_password": "abc123", "is_admin": "false"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "new-user").one()
        user_id = user.id
    finally:
        db.close()
    updated = client.post(
        f"/users/{user_id}/edit",
        data={"username": "renamed", "is_active": "true", "is_admin": "false", "new_password": "", "confirm_password": ""},
        follow_redirects=False,
    )
    assert updated.status_code == 303
    assert client.post(f"/users/{user_id}/delete", follow_redirects=False).status_code == 303


def test_user_create_persistence_error_is_shown_in_form(client, admin_user, monkeypatch):
    login(client)

    def fail_commit(_session):
        raise OperationalError("INSERT", {}, Exception("readonly"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post(
        "/users/new",
        data={
            "username": "cannot-save", "password": "abc123",
            "confirm_password": "abc123", "is_admin": "false",
        },
    )
    assert response.status_code == 400
    assert "用户保存失败" in response.text


def test_operation_logs_are_created(client, admin_user):
    login(client)
    client.post("/orders", data=order_payload())
    order = get_order()
    client.post(f"/orders/{order.id}/paid")
    db = SessionLocal()
    try:
        assert db.query(OperationLog).filter(OperationLog.target_id == order.id).count() == 1
    finally:
        db.close()
