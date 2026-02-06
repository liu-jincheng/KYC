"""
认证服务模块
"""
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
import json
import hashlib
import time

from app.database import get_db, SessionLocal
from app.models import User, UserRole


# Session 配置
SESSION_COOKIE_NAME = "kyc_session"
SESSION_SECRET = "kyc_crm_session_secret_2024"  # 生产环境应使用环境变量
SESSION_MAX_AGE = 86400 * 7  # 7 天


def create_session_token(user_id: int) -> str:
    """
    创建会话令牌
    
    格式: user_id:timestamp:signature
    """
    timestamp = int(time.time())
    data = f"{user_id}:{timestamp}"
    signature = hashlib.sha256(f"{data}:{SESSION_SECRET}".encode()).hexdigest()[:16]
    return f"{data}:{signature}"


def verify_session_token(token: str) -> Optional[int]:
    """
    验证会话令牌并返回用户 ID
    
    返回 None 表示令牌无效或已过期
    """
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        
        user_id = int(parts[0])
        timestamp = int(parts[1])
        signature = parts[2]
        
        # 验证签名
        expected_signature = hashlib.sha256(
            f"{user_id}:{timestamp}:{SESSION_SECRET}".encode()
        ).hexdigest()[:16]
        
        if signature != expected_signature:
            return None
        
        # 验证是否过期
        if time.time() - timestamp > SESSION_MAX_AGE:
            return None
        
        return user_id
    except (ValueError, IndexError):
        return None


def get_current_user_from_request(request: Request) -> Optional[User]:
    """
    从请求中获取当前登录用户
    
    用于页面路由（不抛出异常）
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return None
    
    user_id = verify_session_token(session_token)
    if not user_id:
        return None
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
        return user
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    获取当前登录用户（API 依赖项）
    
    未登录时抛出 401 异常
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise HTTPException(status_code=401, detail="请先登录")
    
    user_id = verify_session_token(session_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")
    
    user = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    获取当前登录用户（可选，不抛出异常）
    
    用于需要兼容未登录状态的场景
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return None
    
    user_id = verify_session_token(session_token)
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    要求管理员权限（API 依赖项）
    
    非管理员抛出 403 异常
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def check_customer_access(customer_owner_id: Optional[int], current_user: User) -> bool:
    """
    检查用户是否有权访问指定客户
    
    管理员可访问所有客户
    普通用户只能访问自己的客户（owner_user_id 为空的客户视为公共）
    """
    if current_user.is_admin:
        return True
    
    # owner_user_id 为空的客户，所有用户可访问（历史数据兼容）
    if customer_owner_id is None:
        return True
    
    return customer_owner_id == current_user.id
