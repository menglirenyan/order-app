def format_money(value) -> str:
    return f"{float(value or 0):.2f}"


def action_label(action: str) -> str:
    labels = {
        "mark_printed": "打印出货单并标记拉走",
        "mark_paid": "标记结清",
        "mark_unpaid": "改回未结清",
        "record_payment": "登记本次收款",
        "mark_delivered": "标记拉走",
        "undo_payment_status": "撤回付款状态",
        "undo_print_status": "撤回打印/拉走状态",
        "undo_delivery_status": "撤回拉走状态",
        "edit_order": "编辑订单",
        "delete_order": "删除订单",
    }
    return labels.get(action, action)
