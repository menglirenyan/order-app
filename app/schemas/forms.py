"""Typed internal inputs shared by routers and domain services."""

from dataclasses import dataclass


@dataclass
class OrderFormData:
    customer: str
    phone: str
    order_type: str
    item_name: str
    size: str
    quantity: int
    unit_price: float
    paid_amount: float
    remark: str


@dataclass
class OrderListFilters:
    keyword: str = ""
    order_type: str = ""
    payment_status: str = ""
    delivery_status: str = ""
    print_status: str = ""
    date_from: str = ""
    date_to: str = ""
    sort_by: str = "risk_first"
    page: int = 1
    per_page: int = 50
