"""
仪表盘 API 路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Customer, CustomerStatus
from app.schemas import DashboardStats, DashboardReminders
from app.services.reminder_service import get_all_reminders

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """获取仪表盘统计数据（使用 GROUP BY 优化查询）"""
    # 单次 GROUP BY 查询替代 6 次 COUNT
    status_counts = (
        db.query(Customer.status, func.count(Customer.id))
        .filter(Customer.is_deleted == 0)
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
def get_reminders(db: Session = Depends(get_db)):
    """
    获取待办提醒

    - 跟进提醒: next_follow_up <= today 的客户
    - 生日提醒: 仅当 birthday 字段非空时计算(7天内生日)
    - 状态滞留: 状态为"AI分析中"超过3天的客户
    """
    return get_all_reminders(db)
