"""
表单邀请 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import FormInvite, Customer, FormTemplate, User
from app.schemas import InviteCreate, InviteResponse, InviteFormData, InviteValidateResponse
from app.services.auth_service import get_current_user_optional, check_customer_access

router = APIRouter()


@router.post("", response_model=InviteResponse)
def create_invite(
    invite_data: InviteCreate,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    为指定客户创建表单填写邀请链接
    
    - 生成唯一的访问令牌
    - 设置过期时间（默认7天）
    - 返回完整的邀请链接
    """
    # 检查客户是否存在
    customer = db.query(Customer).filter(Customer.id == invite_data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 权限检查
    if current_user and not check_customer_access(customer.owner_user_id, current_user):
        raise HTTPException(status_code=403, detail="无权为此客户生成填写链接")
    
    # 计算过期时间
    expires_at = None
    if invite_data.expires_days and invite_data.expires_days > 0:
        expires_at = datetime.now() + timedelta(days=invite_data.expires_days)
    
    # 创建邀请记录
    invite = FormInvite(
        customer_id=invite_data.customer_id,
        token=FormInvite.generate_token(),
        expires_at=expires_at,
        is_active=1,
        created_by_user_id=current_user.id if current_user else None
    )
    
    db.add(invite)
    db.commit()
    db.refresh(invite)
    
    # 构建完整的邀请链接
    base_url = str(request.base_url).rstrip("/")
    invite_url = f"{base_url}/fill/{invite.token}"
    
    return InviteResponse(
        id=invite.id,
        customer_id=invite.customer_id,
        token=invite.token,
        expires_at=invite.expires_at,
        is_active=invite.is_active,
        used_at=invite.used_at,
        created_at=invite.created_at,
        invite_url=invite_url
    )


@router.get("/{token}/validate", response_model=InviteValidateResponse)
def validate_invite(
    token: str,
    db: Session = Depends(get_db)
):
    """
    验证邀请链接是否有效
    
    返回客户姓名和表单结构（用于渲染表单）
    """
    # 查找邀请记录
    invite = db.query(FormInvite).filter(FormInvite.token == token).first()
    
    if not invite:
        return InviteValidateResponse(
            valid=False,
            message="邀请链接无效"
        )
    
    # 检查是否已使用
    if invite.used_at is not None:
        return InviteValidateResponse(
            valid=False,
            message="该链接已被使用"
        )
    
    # 检查是否已过期
    if invite.expires_at and invite.expires_at < datetime.now():
        return InviteValidateResponse(
            valid=False,
            message="邀请链接已过期"
        )
    
    # 检查是否被禁用
    if invite.is_active != 1:
        return InviteValidateResponse(
            valid=False,
            message="邀请链接已失效"
        )
    
    # 获取客户信息
    customer = db.query(Customer).filter(Customer.id == invite.customer_id).first()
    if not customer:
        return InviteValidateResponse(
            valid=False,
            message="关联的客户不存在"
        )
    
    # 获取当前激活的表单配置
    form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
    
    return InviteValidateResponse(
        valid=True,
        message="邀请链接有效",
        customer_name=customer.name,
        form_schema=form_template.schema if form_template else None
    )


@router.post("/{token}/submit")
def submit_invite_form(
    token: str,
    form_data: InviteFormData,
    db: Session = Depends(get_db)
):
    """
    通过邀请链接提交表单数据
    
    - 验证令牌有效性
    - 将表单数据写入客户记录
    - 标记邀请链接为已使用
    """
    # 查找邀请记录
    invite = db.query(FormInvite).filter(FormInvite.token == token).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="邀请链接无效")
    
    # 检查是否已使用
    if invite.used_at is not None:
        raise HTTPException(status_code=400, detail="该链接已被使用")
    
    # 检查是否已过期
    if invite.expires_at and invite.expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="邀请链接已过期")
    
    # 检查是否被禁用
    if invite.is_active != 1:
        raise HTTPException(status_code=400, detail="邀请链接已失效")
    
    # 获取客户记录
    customer = db.query(Customer).filter(Customer.id == invite.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="关联的客户不存在")
    
    # 更新客户 KYC 数据
    # 如果已有数据，合并（新数据覆盖旧数据）
    if customer.kyc_data:
        merged_data = {**customer.kyc_data, **form_data.kyc_data}
        customer.kyc_data = merged_data
    else:
        customer.kyc_data = form_data.kyc_data
    
    # 如果表单数据中有姓名，更新客户姓名
    if form_data.kyc_data.get("name"):
        customer.name = form_data.kyc_data["name"]
    
    # 标记邀请链接为已使用
    invite.used_at = datetime.now()
    
    db.commit()
    
    return {
        "success": True,
        "message": "表单提交成功",
        "customer_id": customer.id
    }


@router.get("/customer/{customer_id}", response_model=list)
def get_customer_invites(
    customer_id: int,
    db: Session = Depends(get_db)
):
    """
    获取指定客户的所有邀请链接
    """
    # 检查客户是否存在
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    invites = db.query(FormInvite).filter(
        FormInvite.customer_id == customer_id
    ).order_by(FormInvite.created_at.desc()).all()
    
    return [
        {
            "id": inv.id,
            "token": inv.token,
            "expires_at": inv.expires_at,
            "is_active": inv.is_active,
            "used_at": inv.used_at,
            "created_at": inv.created_at
        }
        for inv in invites
    ]


@router.delete("/{invite_id}")
def deactivate_invite(
    invite_id: int,
    db: Session = Depends(get_db)
):
    """
    禁用指定的邀请链接
    """
    invite = db.query(FormInvite).filter(FormInvite.id == invite_id).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="邀请链接不存在")
    
    invite.is_active = 0
    db.commit()
    
    return {"message": "邀请链接已禁用", "id": invite_id}
