"""
仪表盘 API 路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models import Customer, CustomerStatus, User
from app.schemas import DashboardStats, DashboardReminders
from app.services.reminder_service import get_all_reminders
from app.services.auth_service import get_current_user

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取仪表盘统计数据（使用 GROUP BY 优化查询）"""
    query = db.query(Customer).filter(Customer.is_deleted == 0)

    # 权限过滤
    if not current_user.is_admin:
        query = query.filter(
            or_(
                Customer.owner_user_id == current_user.id,
                Customer.owner_user_id.is_(None)
            )
        )

    status_counts = (
        query
        .with_entities(Customer.status, func.count(Customer.id))
        .group_by(Customer.status)
        .all()
    )

    counts = dict(status_counts)
    total = sum(counts.values())

    return DashboardStats(
        total_customers=total,
        pending_count=counts.get(CustomerStatus.PENDING.value, 0),
        analyzing_count=counts.get(CustomerStatus.ANALYZING.value, 0),
        reported_count=counts.get(CustomerStatus.REPORTED.value, 0),
        following_count=counts.get(CustomerStatus.FOLLOWING.value, 0),
        signed_count=counts.get(CustomerStatus.SIGNED.value, 0)
    )


@router.get("/reminders", response_model=DashboardReminders)
def get_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取待办提醒

    - 跟进提醒: next_follow_up <= today 的客户
    - 生日提醒: 仅当 birthday 字段非空时计算(7天内生日)
    - 状态滞留: 状态为"AI分析中"超过3天的客户
    """
    return get_all_reminders(db)
