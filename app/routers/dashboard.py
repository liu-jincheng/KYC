"""
仪表盘 API 路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, CustomerStatus
from app.schemas import DashboardStats, DashboardReminders
from app.services.reminder_service import get_all_reminders

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """获取仪表盘统计数据"""
    total = db.query(Customer).count()
    
    return DashboardStats(
        total_customers=total,
        pending_count=db.query(Customer).filter(
            Customer.status == CustomerStatus.PENDING.value
        ).count(),
        analyzing_count=db.query(Customer).filter(
            Customer.status == CustomerStatus.ANALYZING.value
        ).count(),
        reported_count=db.query(Customer).filter(
            Customer.status == CustomerStatus.REPORTED.value
        ).count(),
        following_count=db.query(Customer).filter(
            Customer.status == CustomerStatus.FOLLOWING.value
        ).count(),
        signed_count=db.query(Customer).filter(
            Customer.status == CustomerStatus.SIGNED.value
        ).count()
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

