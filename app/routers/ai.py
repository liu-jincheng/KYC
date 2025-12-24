"""
AI 相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Literal
import json

from app.database import get_db
from app.models import Customer
from app.services.coze_service import generate_birthday_greeting_via_coze, generate_birthday_greeting_stream

router = APIRouter()


# ============ 请求/响应模型 ============

class BirthdayGreetingRequest(BaseModel):
    """生日祝福生成请求"""
    customer_id: int
    style: Literal["商务专业", "温馨亲切", "幽默风趣", "长辈尊享"] = "商务专业"


class BirthdayGreetingResponse(BaseModel):
    """生日祝福生成响应"""
    success: bool
    message: str
    customer_id: int
    customer_name: str
    greeting: str = ""


# ============ 工具函数 ============

def _safe_get_from_kyc(kyc_data: dict, key: str, default: str = "") -> str:
    """
    从 kyc_data 中安全提取字段值
    
    尝试多种 key 格式：原始 key、小写、带下划线等
    """
    if not kyc_data or not isinstance(kyc_data, dict):
        return default
    
    # 直接匹配
    if key in kyc_data:
        val = kyc_data[key]
        return str(val) if val else default
    
    # 小写匹配
    key_lower = key.lower()
    for k, v in kyc_data.items():
        if k.lower() == key_lower:
            return str(v) if v else default
    
    # 带下划线/驼峰变体
    variants = [
        key.replace("_", ""),  # jobtype
        key.replace("_", "-"),  # job-type
    ]
    for variant in variants:
        for k, v in kyc_data.items():
            if k.lower() == variant.lower():
                return str(v) if v else default
    
    return default


# ============ API 端点 ============

@router.post("/generate-birthday-greeting", response_model=BirthdayGreetingResponse)
async def generate_birthday_greeting(
    request: BirthdayGreetingRequest,
    db: Session = Depends(get_db)
):
    """
    生成 AI 生日祝福
    
    从数据库查询客户信息，提取 name、birthday、job_type、job_title，
    然后调用 Coze 生日工作流生成个性化祝福语。
    """
    # 查询客户
    customer = db.query(Customer).filter(Customer.id == request.customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 检查生日是否已录入
    if not customer.birthday:
        raise HTTPException(
            status_code=400, 
            detail="该客户尚未录入生日信息，请先在客户详情页添加生日"
        )
    
    # 提取数据
    name = customer.name
    birthday_date = customer.birthday.isoformat()  # YYYY-MM-DD
    
    kyc_data = customer.kyc_data or {}
    job_type = _safe_get_from_kyc(kyc_data, "job_type")
    job_title = _safe_get_from_kyc(kyc_data, "job_title")
    
    style = request.style
    
    try:
        # 调用 Coze 生日工作流
        greeting = await generate_birthday_greeting_via_coze(
            name=name,
            birthday_date=birthday_date,
            job_type=job_type,
            job_title=job_title,
            style=style
        )
        
        return BirthdayGreetingResponse(
            success=True,
            message="生成成功",
            customer_id=customer.id,
            customer_name=customer.name,
            greeting=greeting
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成祝福失败: {str(e)}"
        )


@router.post("/generate-birthday-greeting/stream")
async def generate_birthday_greeting_streaming(
    request: BirthdayGreetingRequest,
    db: Session = Depends(get_db)
):
    """
    生成 AI 生日祝福 - 流式输出版本
    
    使用 Server-Sent Events (SSE) 实时返回生成结果
    """
    # 查询客户
    customer = db.query(Customer).filter(Customer.id == request.customer_id).first()
    
    if not customer:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': '客户不存在'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    
    # 检查生日是否已录入
    if not customer.birthday:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': '该客户尚未录入生日信息'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    
    # 提取数据
    name = customer.name
    birthday_date = customer.birthday.isoformat()
    
    kyc_data = customer.kyc_data or {}
    job_type = _safe_get_from_kyc(kyc_data, "job_type")
    job_title = _safe_get_from_kyc(kyc_data, "job_title")
    
    style = request.style
    
    async def generate_stream():
        """生成 SSE 流"""
        try:
            async for chunk in generate_birthday_greeting_stream(
                name=name,
                birthday_date=birthday_date,
                job_type=job_type,
                job_title=job_title,
                style=style
            ):
                yield chunk
        except Exception as e:
            print(f"❌ 流式处理异常: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

