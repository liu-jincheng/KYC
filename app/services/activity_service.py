"""
活动日志服务 - 记录客户操作
"""
from sqlalchemy.orm import Session
from app.models import ActivityLog


def log_activity(
    db: Session,
    customer_id: int | None,
    action_type: str,
    action_detail: dict | None = None,
    user_id: int | None = None,
    auto_commit: bool = False
):
    """
    记录一条活动日志

    Args:
        db: 数据库会话
        customer_id: 客户ID（可为空，如客户已删除）
        action_type: 操作类型
        action_detail: 操作详情（JSON）
        user_id: 操作用户ID
        auto_commit: 是否自动提交（默认不提交，由调用方统一 commit）
    """
    log = ActivityLog(
        customer_id=customer_id,
        user_id=user_id,
        action_type=action_type,
        action_detail=action_detail
    )
    db.add(log)
    if auto_commit:
        db.commit()
