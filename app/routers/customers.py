"""
客户管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import Customer, CustomerStatus
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerStatusUpdate,
    CustomerBirthdayUpdate
)

router = APIRouter()


@router.get("", response_model=CustomerListResponse)
def get_customers(
    status: Optional[str] = Query(None, description="按状态筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取客户列表（支持状态筛选）"""
    query = db.query(Customer)
    
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
    db: Session = Depends(get_db)
):
    """创建新客户"""
    customer = Customer(
        name=customer_data.name,
        kyc_data=customer_data.kyc_data,
        related_contacts=customer_data.related_contacts,
        next_follow_up=customer_data.next_follow_up,
        birthday=customer_data.birthday,
        status=CustomerStatus.PENDING.value
    )
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db)
):
    """获取客户详情"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_db)
):
    """更新客户信息"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 更新非空字段
    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    db.commit()
    db.refresh(customer)
    
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}/status", response_model=CustomerResponse)
def update_customer_status(
    customer_id: int,
    status_data: CustomerStatusUpdate,
    db: Session = Depends(get_db)
):
    """更新客户状态"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    customer.status = status_data.status.value
    db.commit()
    db.refresh(customer)
    
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}/birthday", response_model=CustomerResponse)
def update_customer_birthday(
    customer_id: int,
    birthday_data: CustomerBirthdayUpdate,
    db: Session = Depends(get_db)
):
    """
    更新客户生日（预留接口）
    MVP阶段默认表单不收集生日，但提供此接口以便后续手动更新
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    customer.birthday = birthday_data.birthday
    db.commit()
    db.refresh(customer)
    
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db)
):
    """删除客户"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    db.delete(customer)
    db.commit()
    
    return {"message": "客户已删除", "id": customer_id}

