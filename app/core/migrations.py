from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ..db import Base, engine


def ensure_schema(database_engine: Engine = engine) -> None:
    """Apply the idempotent compatibility changes used by existing SQLite data."""
    Base.metadata.create_all(bind=database_engine)
    inspector = inspect(database_engine)

    if "showcase_items" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("showcase_items")}
        if "category" not in columns:
            with database_engine.begin() as conn:
                conn.execute(text("ALTER TABLE showcase_items ADD COLUMN category VARCHAR DEFAULT '未分类'"))
        if "item_code" not in columns:
            with database_engine.begin() as conn:
                conn.execute(text("ALTER TABLE showcase_items ADD COLUMN item_code VARCHAR DEFAULT ''"))
        with database_engine.begin() as conn:
            rows = conn.execute(text(
                "SELECT id, COALESCE(category, '未分类') AS category "
                "FROM showcase_items "
                "WHERE item_code IS NULL OR item_code = '' "
                "ORDER BY COALESCE(category, '未分类') ASC, created_at ASC, id ASC"
            )).fetchall()
            counter_rows = conn.execute(text(
                "SELECT COALESCE(category, '未分类') AS category, COUNT(*) AS item_count "
                "FROM showcase_items "
                "WHERE item_code IS NOT NULL AND item_code != '' "
                "GROUP BY COALESCE(category, '未分类')"
            )).fetchall()
            counters = {
                (row._mapping["category"] or "未分类").strip() or "未分类": row._mapping["item_count"]
                for row in counter_rows
            }
            for row in rows:
                category = (row._mapping["category"] or "未分类").strip() or "未分类"
                counters[category] = counters.get(category, 0) + 1
                conn.execute(
                    text("UPDATE showcase_items SET item_code = :code WHERE id = :id"),
                    {"code": f"{category}-{counters[category]:03d}", "id": row._mapping["id"]},
                )

    if "orders" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("orders")}
        with database_engine.begin() as conn:
            if "order_type" not in columns:
                conn.execute(text("ALTER TABLE orders ADD COLUMN order_type VARCHAR DEFAULT '瓦楞板'"))
            if "delivery_status" not in columns:
                conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_status VARCHAR DEFAULT '未拉走'"))
            if "delivered_at" not in columns:
                conn.execute(text("ALTER TABLE orders ADD COLUMN delivered_at DATETIME"))

        with database_engine.begin() as conn:
            legacy_payment_count = conn.execute(text(
                "SELECT COUNT(*) FROM orders WHERE payment_status IN ('部分付款', '未付款', '已付款')"
            )).scalar() or 0
            if legacy_payment_count:
                conn.execute(text(
                    "UPDATE orders SET payment_status = "
                    "CASE WHEN payment_status = '已付款' THEN '已结清' ELSE '未结清' END "
                    "WHERE payment_status IN ('部分付款', '未付款', '已付款')"
                ))

            stale_unpaid_count = conn.execute(text(
                "SELECT COUNT(*) FROM orders "
                "WHERE unpaid_amount != CASE "
                "WHEN payment_status = '已结清' THEN 0 "
                "WHEN total_amount - paid_amount > 0 THEN total_amount - paid_amount "
                "ELSE 0 END"
            )).scalar() or 0
            if stale_unpaid_count:
                conn.execute(text(
                    "UPDATE orders SET unpaid_amount = CASE "
                    "WHEN payment_status = '已结清' THEN 0 "
                    "WHEN total_amount - paid_amount > 0 THEN total_amount - paid_amount "
                    "ELSE 0 END"
                ))

            conn.execute(text("UPDATE orders SET order_type = '瓦楞板' WHERE order_type IS NULL OR order_type = ''"))
            conn.execute(text("UPDATE orders SET delivery_status = '未拉走' WHERE delivery_status IS NULL OR delivery_status = ''"))


def initialize_database() -> None:
    ensure_schema(engine)
