"""
客户管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from datetime import datetime
import math

from app.database import get_db
from app.models import Customer, CustomerStatus, User, FormInvite
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerStatusUpdate,
    CustomerBirthdayUpdate,
    BatchStatusUpdate,
    BatchDeleteRequest,
    BatchRestoreRequest,
    BatchOperationResponse,
    DuplicateCheckResponse,
)
from app.services.auth_service import (
    get_current_user, get_current_user_optional, check_customer_access
)
from app.services.activity_service import log_activity

router = APIRouter()


def base_customer_query(db: Session):
    """基础查询：排除已软删除的客户"""
    return db.query(Customer).filter(Customer.is_deleted == 0)


# ============ 静态路由（必须在 /{customer_id} 之前声明） ============

@router.get("/check-duplicate", response_model=DuplicateCheckResponse)
def check_duplicate(
    name: str = Query(..., min_length=1, description="客户姓名"),
    exclude_id: Optional[int] = Query(None, description="排除的客户ID（编辑时用）"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """检测客户姓名是否重复"""
    query = base_customer_query(db).filter(Customer.name == name)
    if exclude_id:
        query = query.filter(Customer.id != exclude_id)

    duplicates = query.all()
    return DuplicateCheckResponse(
        has_duplicate=len(duplicates) > 0,
        duplicates=[
            {"id": c.id, "name": c.name, "status": c.status}
            for c in duplicates
        ]
    )


@router.get("/recycle-bin", response_model=CustomerListResponse)
def get_recycle_bin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取回收站列表（已软删除的客户）"""
    query = db.query(Customer).filter(Customer.is_deleted == 1)

    # 权限过滤
    if current_user and not current_user.is_admin:
        query = query.filter(
            or_(
                Customer.owner_user_id == current_user.id,
                Customer.owner_user_id.is_(None)
            )
        )

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    skip = (page - 1) * page_size
    customers = query.order_by(Customer.deleted_at.desc()).offset(skip).limit(page_size).all()

    return CustomerListResponse(
        total=total,
        items=[CustomerResponse.model_validate(c) for c in customers],
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.put("/batch/status", response_model=BatchOperationResponse)
def batch_update_status(
    data: BatchStatusUpdate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """批量修改客户状态"""
    customers = base_customer_query(db).filter(
        Customer.id.in_(data.customer_ids)
    ).all()

    # 权限过滤
    accessible = []
    for c in customers:
        if not current_user or check_customer_access(c.owner_user_id, current_user):
            accessible.append(c)

    for c in accessible:
        old_status = c.status
        c.status = data.status.value
        log_activity(
            db, c.id, "status_changed",
            {"from_status": old_status, "to_status": data.status.value},
            user_id=current_user.id if current_user else None
        )

    db.commit()
    return BatchOperationResponse(
        success=True,
        message=f"已更新 {len(accessible)} 个客户状态",
        affected_count=len(accessible)
    )


@router.post("/batch/delete", response_model=BatchOperationResponse)
def batch_delete(
    data: BatchDeleteRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """批量软删除客户"""
    customers = base_customer_query(db).filter(
        Customer.id.in_(data.customer_ids)
    ).all()

    accessible = []
    for c in customers:
        if not current_user or check_customer_access(c.owner_user_id, current_user):
            accessible.append(c)

    now = datetime.now()
    for c in accessible:
        c.is_deleted = 1
        c.deleted_at = now
        log_activity(
            db, c.id, "customer_deleted",
            {"name": c.name},
            user_id=current_user.id if current_user else None
        )

    db.commit()
    return BatchOperationResponse(
        success=True,
        message=f"已将 {len(accessible)} 个客户移入回收站",
        affected_count=len(accessible)
    )


@router.post("/batch/restore", response_model=BatchOperationResponse)
def batch_restore(
    data: BatchRestoreRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """批量恢复已删除客户"""
    customers = db.query(Customer).filter(
        Customer.id.in_(data.customer_ids),
        Customer.is_deleted == 1
    ).all()

    accessible = []
    for c in customers:
        if not current_user or check_customer_access(c.owner_user_id, current_user):
            accessible.append(c)

    for c in accessible:
        c.is_deleted = 0
        c.deleted_at = None
        log_activity(
            db, c.id, "customer_restored",
            {"name": c.name},
            user_id=current_user.id if current_user else None
        )

    db.commit()
    return BatchOperationResponse(
        success=True,
        message=f"已恢复 {len(accessible)} 个客户",
        affected_count=len(accessible)
    )


# ============ 标准 CRUD 路由 ============

@router.get("", response_model=CustomerListResponse)
def get_customers(
    status: Optional[str] = Query(None, description="按状态筛选"),
    statuses: Optional[str] = Query(None, description="逗号分隔多状态筛选"),
    search: Optional[str] = Query(None, description="按姓名搜索"),
    owner_id: Optional[int] = Query(None, description="按归属顾问筛选（0=未分配）"),
    date_from: Optional[str] = Query(None, description="创建日期起始 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="创建日期截止 YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=999, description="每页条数"),
    skip: int = Query(None, ge=0, description="跳过条数（兼容旧参数）"),
    limit: int = Query(None, ge=1, le=999, description="返回条数（兼容旧参数）"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取客户列表（支持状态筛选、搜索、分页）

    权限规则：
    - 管理员：可查看所有客户
    - 普通用户：只能查看自己的客户 + owner_user_id 为空的客户
    - 未登录：可查看所有客户（兼容旧版本）
    """
    query = base_customer_query(db)

    # 权限过滤
    if current_user and not current_user.is_admin:
        query = query.filter(
            or_(
                Customer.owner_user_id == current_user.id,
                Customer.owner_user_id.is_(None)
            )
        )

    # 状态筛选（支持单个或多个）
    if statuses:
        status_list = [s.strip() for s in statuses.split(",") if s.strip()]
        if status_list:
            query = query.filter(Customer.status.in_(status_list))
    elif status:
        query = query.filter(Customer.status == status)

    # 姓名搜索
    if search:
        query = query.filter(Customer.name.ilike(f"%{search}%"))

    # 按归属顾问筛选
    if owner_id is not None:
        if owner_id == 0:
            query = query.filter(Customer.owner_user_id.is_(None))
        else:
            query = query.filter(Customer.owner_user_id == owner_id)

    # 创建日期范围筛选
    if date_from:
        try:
            from datetime import datetime as dt
            d = dt.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Customer.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime as dt
            d = dt.strptime(date_to, "%Y-%m-%d")
            # 包含当天，截止到次日 00:00
            from datetime import timedelta
            query = query.filter(Customer.created_at < d + timedelta(days=1))
        except ValueError:
            pass

    total = query.count()

    # 兼容旧 skip/limit 参数
    if skip is not None and limit is not None:
        actual_skip = skip
        actual_limit = limit
        actual_page = (skip // limit) + 1 if limit > 0 else 1
        actual_page_size = limit
    else:
        actual_page = page
        actual_page_size = page_size
        actual_skip = (page - 1) * page_size
        actual_limit = page_size

    total_pages = max(1, math.ceil(total / actual_page_size)) if actual_page_size > 0 else 1
    customers = query.order_by(Customer.created_at.desc()).offset(actual_skip).limit(actual_limit).all()

    return CustomerListResponse(
        total=total,
        items=[CustomerResponse.model_validate(c) for c in customers],
        page=actual_page,
        page_size=actual_page_size,
        total_pages=total_pages
    )


@router.post("", response_model=CustomerResponse)
def create_customer(
    customer_data: CustomerCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    创建新客户

    - 管理员可以指定归属用户
    - 普通用户自动归属到自己
    - 未登录时不设置归属
    """
    # 确定归属用户
    owner_id = None
    if current_user:
        if current_user.is_admin and customer_data.owner_user_id is not None:
            # 管理员可以指定归属
            owner_id = customer_data.owner_user_id if customer_data.owner_user_id > 0 else None
        else:
            # 普通用户归属到自己
            owner_id = current_user.id

    customer = Customer(
        name=customer_data.name,
        kyc_data=customer_data.kyc_data,
        related_contacts=customer_data.related_contacts,
        next_follow_up=customer_data.next_follow_up,
        birthday=customer_data.birthday,
        status=CustomerStatus.PENDING.value,
        owner_user_id=owner_id
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    log_activity(
        db, customer.id, "customer_created",
        {"name": customer.name},
        user_id=current_user.id if current_user else None,
        auto_commit=True
    )

    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取客户详情"""
    customer = base_customer_query(db).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权访问此客户")

    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """更新客户信息"""
    customer = base_customer_query(db).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权修改此客户")

    # 更新非空字段
    update_data = customer_data.model_dump(exclude_unset=True)

    # 记录哪些字段被更新（用于日志）
    old_follow_up = str(customer.next_follow_up) if customer.next_follow_up else None

    # owner_user_id 只允许管理员修改
    if 'owner_user_id' in update_data:
        if not current_user or not current_user.is_admin:
            del update_data['owner_user_id']
        elif update_data['owner_user_id'] == 0:
            update_data['owner_user_id'] = None

    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)

    # 记录活动日志
    log_activity(
        db, customer_id, "customer_updated",
        {"updated_fields": list(update_data.keys())},
        user_id=current_user.id if current_user else None
    )
    # 如果跟进日期变化，额外记录
    new_follow_up = str(customer.next_follow_up) if customer.next_follow_up else None
    if 'next_follow_up' in update_data and new_follow_up != old_follow_up:
        log_activity(
            db, customer_id, "follow_up_changed",
            {"new_date": new_follow_up},
            user_id=current_user.id if current_user else None
        )
    db.commit()

    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}/status", response_model=CustomerResponse)
def update_customer_status(
    customer_id: int,
    status_data: CustomerStatusUpdate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """更新客户状态"""
    customer = base_customer_query(db).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权修改此客户")

    old_status = customer.status
    customer.status = status_data.status.value
    log_activity(
        db, customer_id, "status_changed",
        {"from_status": old_status, "to_status": status_data.status.value},
        user_id=current_user.id if current_user else None
    )
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}/birthday", response_model=CustomerResponse)
def update_customer_birthday(
    customer_id: int,
    birthday_data: CustomerBirthdayUpdate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    更新客户生日（预留接口）
    MVP阶段默认表单不收集生日，但提供此接口以便后续手动更新
    """
    customer = base_customer_query(db).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权修改此客户")

    customer.birthday = birthday_data.birthday
    log_activity(
        db, customer_id, "birthday_updated",
        {"new_date": str(birthday_data.birthday) if birthday_data.birthday else None},
        user_id=current_user.id if current_user else None
    )
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}/owner", response_model=CustomerResponse)
def update_customer_owner(
    customer_id: int,
    owner_user_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新客户归属（管理员接口）

    - 管理员可以将客户分配给任意用户
    - owner_user_id 为 None 表示取消归属（公共客户）
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    customer = base_customer_query(db).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 如果指定了用户ID，检查用户是否存在
    if owner_user_id is not None:
        owner = db.query(User).filter(User.id == owner_user_id).first()
        if not owner:
            raise HTTPException(status_code=404, detail="指定的用户不存在")

    customer.owner_user_id = owner_user_id
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/restore", response_model=CustomerResponse)
def restore_customer(
    customer_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """恢复已删除的客户"""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == 1
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在或未被删除")

    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权操作此客户")

    customer.is_deleted = 0
    customer.deleted_at = None
    log_activity(
        db, customer_id, "customer_restored",
        {"name": customer.name},
        user_id=current_user.id if current_user else None
    )
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """软删除客户（移入回收站）"""
    customer = base_customer_query(db).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权删除此客户")

    # 记录删除日志
    log_activity(
        db, customer_id, "customer_deleted",
        {"name": customer.name},
        user_id=current_user.id if current_user else None
    )

    # 软删除
    customer.is_deleted = 1
    customer.deleted_at = datetime.now()
    db.commit()

    return {"message": "客户已移入回收站", "id": customer_id}


@router.delete("/{customer_id}/permanent")
def permanent_delete_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """永久删除客户（仅管理员，需先软删除）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == 1
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在或未在回收站中")

    # 记录日志
    log_activity(
        db, customer_id, "customer_permanent_deleted",
        {"name": customer.name},
        user_id=current_user.id
    )

    # 先删除关联的邀请记录
    db.query(FormInvite).filter(FormInvite.customer_id == customer_id).delete()

    db.delete(customer)
    db.commit()

    return {"message": "客户已永久删除", "id": customer_id}
