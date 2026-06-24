from sqlalchemy.orm import Session

from ..models import OperationLog


def log_operation(
    db: Session,
    target_type: str,
    target_id: int,
    action: str,
    field_name: str,
    old_value: str,
    new_value: str,
    operator: str,
) -> None:
    db.add(OperationLog(
        target_type=target_type,
        target_id=target_id,
        action=action,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        operator=operator,
    ))


def get_latest_reversible_log(db: Session, order_id: int):
    reversible_actions = ["mark_printed", "mark_paid", "mark_unpaid", "record_payment", "mark_delivered"]
    undo_actions = ["undo_print_status", "undo_payment_status", "undo_delivery_status"]
    latest_undo = (
        db.query(OperationLog)
        .filter(
            OperationLog.target_type == "order",
            OperationLog.target_id == order_id,
            OperationLog.action.in_(undo_actions),
        )
        .order_by(OperationLog.id.desc())
        .first()
    )
    query = db.query(OperationLog).filter(
        OperationLog.target_type == "order",
        OperationLog.target_id == order_id,
        OperationLog.action.in_(reversible_actions),
    )
    if latest_undo is not None:
        query = query.filter(OperationLog.id > latest_undo.id)
    return query.order_by(OperationLog.id.desc()).first()
