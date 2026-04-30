from datetime import datetime, date

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Date
from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True, nullable=False)

    customer = Column(String, index=True, nullable=False)
    phone = Column(String, default="")
    item_name = Column(String, index=True, nullable=False)
    size = Column(String, default="")

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)

    paid_amount = Column(Float, default=0.0)
    unpaid_amount = Column(Float, default=0.0)

    payment_status = Column(String, default="未付款")
    production_status = Column(String, default="未投产")
    print_status = Column(String, default="未打印")

    priority_color = Column(String, default="灰色")   # 红色 / 橙色 / 黄色 / 蓝色 / 灰色
    due_date = Column(Date, nullable=True)

    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, index=True, nullable=False)
    status = Column(String, default="pending", index=True)  # pending / printing / done / failed
    client_id = Column(String, default="")
    attempts = Column(Integer, default=0)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    claimed_at = Column(DateTime, nullable=True)
    printed_at = Column(DateTime, nullable=True)


class ShowcaseItem(Base):
    __tablename__ = "showcase_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    category = Column(String, default="未分类", index=True)
    image_url = Column(String, default="")
    description = Column(Text, default="")
    sort_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String, nullable=False)       # order / user / showcase
    target_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)            # mark_printed / mark_production / mark_complete / edit_order / delete_order ...
    field_name = Column(String, default="")            # print_status / production_status ...
    old_value = Column(Text, default="")
    new_value = Column(Text, default="")
    operator = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
