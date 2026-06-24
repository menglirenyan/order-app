from sqlalchemy import create_engine, inspect, text

from app.core.migrations import ensure_schema


def test_legacy_order_schema_is_upgraded_without_losing_rows(tmp_path):
    database = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                order_no VARCHAR NOT NULL,
                customer VARCHAR NOT NULL,
                phone VARCHAR,
                item_name VARCHAR NOT NULL,
                size VARCHAR,
                quantity INTEGER NOT NULL,
                unit_price FLOAT NOT NULL,
                total_amount FLOAT NOT NULL,
                paid_amount FLOAT,
                unpaid_amount FLOAT,
                payment_status VARCHAR,
                print_status VARCHAR,
                priority_color VARCHAR,
                due_date DATE,
                remark TEXT,
                created_at DATETIME
            )
        """))
        connection.execute(text("""
            INSERT INTO orders (
                id, order_no, customer, item_name, quantity, unit_price, total_amount,
                paid_amount, unpaid_amount, payment_status, print_status
            ) VALUES (1, '20260101-001', '客户', '商品', 1, 100, 100, 20, 999, '部分付款', '未打印')
        """))
    ensure_schema(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("orders")}
    assert {"order_type", "delivery_status", "delivered_at"}.issubset(columns)
    with engine.begin() as connection:
        row = connection.execute(text(
            "SELECT payment_status, unpaid_amount, order_type, delivery_status FROM orders WHERE id = 1"
        )).one()
    assert tuple(row) == ("未结清", 80, "瓦楞板", "未拉走")
