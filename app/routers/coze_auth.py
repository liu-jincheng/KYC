"""
Coze OAuth 2.0 授权路由

提供管理员一次性授权流程：
- /coze/auth/login  -> 跳转到 Coze 授权页面
- /callback         -> 接收授权码并换取 Token
"""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from app.services.coze_oauth_service import (
    build_authorize_url,
    exchange_code_for_token,
    save_token_to_db,
)

router = APIRouter()


@router.get("/coze/auth/login")
async def coze_auth_login():
    """
    管理员授权入口
    
    生成 Coze OAuth 授权 URL 并重定向用户浏览器到 Coze 授权页面。
    用户在 Coze 授权后，会被重定向回 /callback。
    """
    authorize_url = build_authorize_url()
    return RedirectResponse(url=authorize_url)


@router.get("/callback")
async def coze_auth_callback(request: Request, code: str = None, error: str = None):
    """
    Coze OAuth 回调端点
    
    接收 Coze 授权服务器返回的授权码，换取 Token 并存入数据库。
    
    Query Params:
        code: 授权码（成功时）
        error: 错误信息（失败时）
    """
    # 处理授权失败
    if error:
        return HTMLResponse(
            content=f"""
            <html>
            <head><meta charset="utf-8"><title>授权失败</title></head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                         max-width: 600px; margin: 100px auto; text-align: center;">
                <h1 style="color: #e74c3c;">❌ Coze 授权失败</h1>
                <p style="color: #666;">错误信息: {error}</p>
                <a href="/coze/auth/login" style="color: #3498db;">重新授权</a>
                <span style="margin: 0 10px;">|</span>
                <a href="/" style="color: #3498db;">返回首页</a>
            </body>
            </html>
            """,
            status_code=400,
        )
    
    # 检查授权码
    if not code:
        return HTMLResponse(
            content="""
            <html>
            <head><meta charset="utf-8"><title>参数缺失</title></head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                         max-width: 600px; margin: 100px auto; text-align: center;">
                <h1 style="color: #e74c3c;">❌ 缺少授权码</h1>
                <p style="color: #666;">回调请求中未包含授权码 (code) 参数。</p>
                <a href="/coze/auth/login" style="color: #3498db;">重新授权</a>
                <span style="margin: 0 10px;">|</span>
                <a href="/" style="color: #3498db;">返回首页</a>
            </body>
            </html>
            """,
            status_code=400,
        )
    
    try:
        # 用授权码换取 Token
        token_data = await exchange_code_for_token(code)
        
        # 存入数据库
        save_token_to_db(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"],
        )
        
        # 返回成功页面
        return HTMLResponse(
            content=f"""
            <html>
            <head><meta charset="utf-8"><title>授权成功</title></head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                         max-width: 600px; margin: 100px auto; text-align: center;">
                <h1 style="color: #27ae60;">✅ Coze OAuth 授权成功!</h1>
                <p style="color: #666;">Token 已安全存储到数据库，系统将自动续期。</p>
                <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: left;">
                    <p><strong>Access Token:</strong> {token_data['access_token'][:20]}...（已隐藏）</p>
                    <p><strong>Refresh Token:</strong> {token_data['refresh_token'][:20]}...（已隐藏）</p>
                    <p><strong>过期时间:</strong> {token_data['expires_in']} 秒</p>
                </div>
                <p style="color: #999; font-size: 14px;">此页面可安全关闭，无需任何额外操作。</p>
                <a href="/" style="display: inline-block; margin-top: 15px; padding: 10px 25px; 
                           background: #3498db; color: white; text-decoration: none; border-radius: 5px;">
                    返回首页
                </a>
            </body>
            </html>
            """
        )
    
    except Exception as e:
        return HTMLResponse(
            content=f"""
            <html>
            <head><meta charset="utf-8"><title>Token 获取失败</title></head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                         max-width: 600px; margin: 100px auto; text-align: center;">
                <h1 style="color: #e74c3c;">❌ Token 获取失败</h1>
                <p style="color: #666;">{str(e)}</p>
                <a href="/coze/auth/login" style="color: #3498db;">重新授权</a>
                <span style="margin: 0 10px;">|</span>
                <a href="/" style="color: #3498db;">返回首页</a>
            </body>
            </html>
            """,
            status_code=500,
        )
