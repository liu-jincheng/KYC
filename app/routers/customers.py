"""
客户管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List

from app.database import get_db
from app.models import Customer, CustomerStatus, User
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerStatusUpdate,
    CustomerBirthdayUpdate
)
from app.services.auth_service import (
    get_current_user, get_current_user_optional, check_customer_access
)

router = APIRouter()


@router.get("", response_model=CustomerListResponse)
def get_customers(
    status: Optional[str] = Query(None, description="按状态筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取客户列表（支持状态筛选）
    
    权限规则：
    - 管理员：可查看所有客户
    - 普通用户：只能查看自己的客户 + owner_user_id 为空的客户
    - 未登录：可查看所有客户（兼容旧版本）
    """
    query = db.query(Customer)
    
    # 权限过滤
    if current_user and not current_user.is_admin:
        # 普通用户只能看自己的客户或未分配的客户
        query = query.filter(
            or_(
                Customer.owner_user_id == current_user.id,
                Customer.owner_user_id.is_(None)
            )
        )
    
    if status:
        query = query.filter(Customer.status == status)
    
    total = query.count()
    customers = query.order_by(Customer.created_at.desc()).offset(skip).limit(limit).all()
    
    return CustomerListResponse(
        total=total,
        items=[CustomerResponse.model_validate(c) for c in customers]
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
    
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取客户详情"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
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
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权修改此客户")
    
    # 更新非空字段
    update_data = customer_data.model_dump(exclude_unset=True)
    
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
    
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}/status", response_model=CustomerResponse)
def update_customer_status(
    customer_id: int,
    status_data: CustomerStatusUpdate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """更新客户状态"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权修改此客户")
    
    customer.status = status_data.status.value
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
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权修改此客户")
    
    customer.birthday = birthday_data.birthday
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
    
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 如果指定了用户ID，检查用户是否存在
    if owner_user_id is not None:
        from app.models import User as UserModel
        owner = db.query(UserModel).filter(UserModel.id == owner_user_id).first()
        if not owner:
            raise HTTPException(status_code=404, detail="指定的用户不存在")
    
    customer.owner_user_id = owner_user_id
    db.commit()
    db.refresh(customer)
    
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """删除客户"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权删除此客户")
    
    db.delete(customer)
    db.commit()
    
    return {"message": "客户已删除", "id": customer_id}
