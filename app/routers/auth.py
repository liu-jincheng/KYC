"""
认证 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    LoginRequest, LoginResponse, UserResponse,
    UserCreate, UserUpdate, UserPasswordUpdate
)
from app.services.auth_service import (
    create_session_token, SESSION_COOKIE_NAME, SESSION_MAX_AGE,
    get_current_user, require_admin
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    用户登录
    
    成功后设置 session cookie
    """
    # 查找用户
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user:
        return LoginResponse(success=False, message="用户名或密码错误")
    
    if not user.is_active:
        return LoginResponse(success=False, message="账户已被禁用")
    
    if not user.verify_password(login_data.password):
        return LoginResponse(success=False, message="用户名或密码错误")
    
    # 创建会话令牌并设置 cookie
    session_token = create_session_token(user.id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax"
    )
    
    return LoginResponse(
        success=True,
        message="登录成功",
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
def logout(response: Response):
    """
    用户登出
    
    清除 session cookie
    """
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"success": True, "message": "已退出登录"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息
    """
    return UserResponse.model_validate(current_user)


@router.put("/me/password")
def change_password(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改当前用户密码
    """
    if not current_user.verify_password(password_data.old_password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    
    current_user.password_hash = User.hash_password(password_data.new_password)
    db.commit()
    
    return {"success": True, "message": "密码修改成功"}


# ============ 管理员接口 ============

@router.get("/users", response_model=list)
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    获取所有用户列表（管理员）
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    创建新用户（管理员）
    """
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    new_user = User(
        username=user_data.username,
        password_hash=User.hash_password(user_data.password),
        display_name=user_data.display_name or user_data.username,
        role=user_data.role.value,
        is_active=1
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse.model_validate(new_user)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    更新用户信息（管理员）
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新字段
    if user_data.display_name is not None:
        user.display_name = user_data.display_name
    if user_data.role is not None:
        user.role = user_data.role.value
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    db.commit()
    db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    重置用户密码（管理员）
    
    重置为默认密码: 123456
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    default_password = "123456"
    user.password_hash = User.hash_password(default_password)
    db.commit()
    
    return {
        "success": True,
        "message": f"密码已重置为: {default_password}"
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    永久删除用户（管理员）
    
    警告：此操作不可逆，将从数据库中永久删除用户
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    username = user.username
    db.delete(user)
    db.commit()
    
    return {"success": True, "message": f"用户 '{username}' 已永久删除"}
