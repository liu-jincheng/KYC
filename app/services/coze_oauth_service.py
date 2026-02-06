"""
Coze OAuth 2.0 服务模块

负责 OAuth 授权码模式的完整流程：
- 构建授权 URL
- 用授权码换取 Token
- 自动刷新 Token
- 提供统一的 get_valid_token() 接口
"""
import time
import logging
import secrets
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models import CozeOAuthToken

logger = logging.getLogger(__name__)

# Token 提前刷新的缓冲时间（秒）：过期前 10 分钟刷新
TOKEN_REFRESH_BUFFER = 600


def get_coze_redirect_uri() -> str:
    """根据运行环境获取对应的回调地址"""
    return settings.COZE_REDIRECT_URI


def build_authorize_url() -> str:
    """
    构建 Coze OAuth 2.0 授权页跳转 URL
    
    Returns:
        完整的授权页 URL，用户浏览器应重定向到此地址
    """
    state = secrets.token_urlsafe(16)
    redirect_uri = get_coze_redirect_uri()
    
    params = {
        "response_type": "code",
        "client_id": settings.COZE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    
    authorize_url = f"{settings.COZE_WWW_BASE_URL}/api/permission/oauth2/authorize?{urlencode(params)}"
    logger.info(f"生成授权 URL: {authorize_url}")
    return authorize_url


async def exchange_code_for_token(code: str) -> dict:
    """
    用授权码换取 access_token 和 refresh_token
    
    Args:
        code: Coze 回调返回的授权码
    
    Returns:
        {"access_token": str, "refresh_token": str, "expires_in": int}
    
    Raises:
        Exception: Token 交换失败时抛出
    """
    token_url = f"{settings.COZE_AUTH_API_BASE_URL}/api/permission/oauth2/token"
    
    # Coze 要求 client_secret 通过 Authorization: Bearer 头传递（非标准）
    headers = {
        "Authorization": f"Bearer {settings.COZE_CLIENT_SECRET}",
        "Content-Type": "application/json",
    }
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": get_coze_redirect_uri(),
        "client_id": settings.COZE_CLIENT_ID,
    }
    
    print("\n" + "=" * 60)
    print("🔑 [COZE OAuth] 用授权码换取 Token")
    print("=" * 60)
    print(f"📍 请求地址: {token_url}")
    print(f"📋 Redirect URI: {payload['redirect_uri']}")
    print("-" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(token_url, headers=headers, json=payload)
        
        print(f"📊 响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            print(f"❌ Token 交换失败: {error_text}")
            logger.error(f"Token 交换失败: {response.status_code} - {error_text}")
            raise Exception(f"Coze Token 交换失败: {response.status_code} - {error_text}")
        
        result = response.json()
        
        # Coze 可能在 JSON 中返回错误
        if result.get("error") or result.get("error_code"):
            error_msg = result.get("error_message", result.get("error", "未知错误"))
            print(f"❌ Token 交换错误: {error_msg}")
            raise Exception(f"Coze Token 交换错误: {error_msg}")
        
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        expires_in = result.get("expires_in", 0)
        
        if not access_token or not refresh_token:
            print(f"❌ 响应缺少 token 字段: {result}")
            raise Exception("Coze 返回数据缺少 access_token 或 refresh_token")
        
        print(f"✅ Token 交换成功!")
        print(f"   access_token: {access_token[:20]}...")
        print(f"   refresh_token: {refresh_token[:20]}...")
        print(f"   expires_in: {expires_in} 秒")
        print("=" * 60 + "\n")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
        }


async def refresh_access_token(refresh_token: str) -> dict:
    """
    使用 refresh_token 刷新 access_token
    
    Coze 实行 Token Rotation：刷新后会返回新的 refresh_token，旧的立即失效。
    
    Args:
        refresh_token: 当前的 refresh_token
    
    Returns:
        {"access_token": str, "refresh_token": str, "expires_in": int}
    
    Raises:
        Exception: 刷新失败时抛出
    """
    token_url = f"{settings.COZE_AUTH_API_BASE_URL}/api/permission/oauth2/token"
    
    # Coze 要求 client_secret 通过 Authorization: Bearer 头传递（非标准）
    headers = {
        "Authorization": f"Bearer {settings.COZE_CLIENT_SECRET}",
        "Content-Type": "application/json",
    }
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.COZE_CLIENT_ID,
    }
    
    print("\n" + "=" * 60)
    print("🔄 [COZE OAuth] 刷新 Token")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(token_url, headers=headers, json=payload)
        
        print(f"📊 响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            print(f"❌ Token 刷新失败: {error_text}")
            logger.error(f"Token 刷新失败: {response.status_code} - {error_text}")
            raise Exception(f"Coze Token 刷新失败: {response.status_code} - {error_text}")
        
        result = response.json()
        
        if result.get("error") or result.get("error_code"):
            error_msg = result.get("error_message", result.get("error", "未知错误"))
            print(f"❌ Token 刷新错误: {error_msg}")
            raise Exception(f"Coze Token 刷新错误: {error_msg}")
        
        new_access_token = result.get("access_token")
        new_refresh_token = result.get("refresh_token")
        expires_in = result.get("expires_in", 0)
        
        if not new_access_token or not new_refresh_token:
            print(f"❌ 刷新响应缺少 token 字段: {result}")
            raise Exception("Coze 刷新返回数据缺少 access_token 或 refresh_token")
        
        print(f"✅ Token 刷新成功!")
        print(f"   新 access_token: {new_access_token[:20]}...")
        print(f"   新 refresh_token: {new_refresh_token[:20]}...")
        print(f"   expires_in: {expires_in} 秒")
        print("=" * 60 + "\n")
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "expires_in": expires_in,
        }


def save_token_to_db(access_token: str, refresh_token: str, expires_in: int) -> None:
    """
    将 OAuth Token 存入数据库
    
    策略：只保留一条最新记录（因为系统只需一组 Coze 凭证）
    
    Args:
        access_token: 访问令牌
        refresh_token: 刷新令牌
        expires_in: Coze 返回的过期时间（Unix 时间戳或秒数）
    """
    db = SessionLocal()
    try:
        # 计算过期时间戳
        # Coze 返回的 expires_in 可能是 Unix 时间戳（很大的数）或剩余秒数
        if expires_in > 1000000000:
            # 已经是 Unix 时间戳
            expires_at = expires_in
        else:
            # 是剩余秒数，转为时间戳
            expires_at = int(time.time()) + expires_in
        
        # 查找已有记录
        existing = db.query(CozeOAuthToken).first()
        
        if existing:
            # 更新已有记录（Token Rotation）
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.expires_at = expires_at
        else:
            # 创建新记录
            token_record = CozeOAuthToken(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            db.add(token_record)
        
        db.commit()
        logger.info(f"Token 已保存到数据库，过期时间戳: {expires_at}")
        print(f"💾 Token 已保存到数据库 (expires_at={expires_at})")
    except Exception as e:
        db.rollback()
        logger.error(f"保存 Token 到数据库失败: {e}")
        raise
    finally:
        db.close()


async def get_valid_token() -> str:
    """
    获取有效的 Coze Access Token（核心函数）
    
    业务逻辑统一通过此函数获取 Token：
    1. 从数据库读取最新的 Token 记录
    2. 检查是否即将过期（剩余 < 10 分钟）
    3. 如果即将过期，使用 refresh_token 自动刷新
    4. Token Rotation：用新的 refresh_token 覆盖旧值
    5. 返回有效的 access_token
    
    Returns:
        有效的 access_token 字符串
    
    Raises:
        Exception: 无可用 Token 或刷新失败时抛出
    """
    db = SessionLocal()
    try:
        # 1. 从数据库获取最新的 Token 记录
        token_record = db.query(CozeOAuthToken).order_by(CozeOAuthToken.id.desc()).first()
        
        if not token_record:
            raise Exception(
                "未找到 Coze OAuth Token，请管理员先访问 /coze/auth/login 完成授权"
            )
        
        current_time = int(time.time())
        time_remaining = token_record.expires_at - current_time
        
        # 2. 检查是否需要刷新
        if time_remaining > TOKEN_REFRESH_BUFFER:
            # Token 仍然有效，直接返回
            logger.debug(f"Token 有效，剩余 {time_remaining} 秒")
            return token_record.access_token
        
        # 3. Token 即将过期或已过期，执行刷新
        print(f"⏰ Token 剩余 {time_remaining} 秒，触发自动刷新...")
        logger.info(f"Token 即将过期（剩余 {time_remaining}s），执行刷新")
        
        try:
            new_tokens = await refresh_access_token(token_record.refresh_token)
        except Exception as e:
            # 刷新失败
            if time_remaining > 0:
                # Token 尚未真正过期，仍可使用
                logger.warning(f"Token 刷新失败但尚未过期，继续使用当前 Token: {e}")
                print(f"⚠️ 刷新失败但 Token 未过期，继续使用 (剩余 {time_remaining}s)")
                return token_record.access_token
            else:
                # Token 已过期且刷新失败
                raise Exception(
                    f"Coze Token 已过期且刷新失败: {e}。请管理员重新访问 /coze/auth/login 授权"
                )
        
        # 4. 刷新成功，保存新 Token（Token Rotation）
        save_token_to_db(
            access_token=new_tokens["access_token"],
            refresh_token=new_tokens["refresh_token"],
            expires_in=new_tokens["expires_in"],
        )
        
        return new_tokens["access_token"]
    
    finally:
        db.close()
