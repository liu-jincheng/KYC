"""
活动日志 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import ActivityLog, User, Customer
from app.schemas import ActivityLogResponse, ActivityLogListResponse
from app.services.auth_service import get_current_user_optional, check_customer_access

router = APIRouter()


@router.get("/{customer_id}", response_model=ActivityLogListResponse)
def get_activity_logs(
    customer_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取客户的活动日志（分页）
    """
    # 检查客户是否存在
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权查看此客户的操作记录")

    query = db.query(ActivityLog).filter(ActivityLog.customer_id == customer_id)
    total = query.count()
    logs = query.order_by(ActivityLog.created_at.desc()).offset(skip).limit(limit).all()

    # 批量查询操作人信息
    user_ids = {log.user_id for log in logs if log.user_id}
    users_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: (u.display_name or u.username) for u in users}

    items = []
    for log in logs:
        item = ActivityLogResponse.model_validate(log)
        item.user_display_name = users_map.get(log.user_id)
        items.append(item)

    return ActivityLogListResponse(total=total, items=items)
