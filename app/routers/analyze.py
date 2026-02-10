"""
AI 分析 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import json

from app.database import get_db
from app.models import Customer, CustomerStatus, User
from app.schemas import AnalyzeResponse
from app.services.coze_service import analyze_customer_kyc, analyze_customer_kyc_stream
from app.services.auth_service import get_current_user
from app.services.activity_service import log_activity

router = APIRouter()


@router.post("/{customer_id}", response_model=AnalyzeResponse)
async def analyze_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    触发 AI 分析
    
    1. 读取客户 KYC 数据
    2. 调用 Coze Workflow API 进行分析
    3. 更新客户 AI 报告和商机
    4. 更新状态为"已出方案"
    """
    # 获取客户
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    if not customer.kyc_data:
        raise HTTPException(status_code=400, detail="客户尚未填写 KYC 表单")
    
    # 更新状态为分析中
    customer.status = CustomerStatus.ANALYZING.value
    log_activity(
        db, customer_id, "ai_analysis_triggered",
        user_id=current_user.id
    )
    db.commit()

    try:
        # 调用 Coze 服务进行分析
        result = await analyze_customer_kyc(
            kyc_data=customer.kyc_data,
            related_contacts=customer.related_contacts
        )

        # 更新客户记录
        customer.ai_report = result.get("report", "")
        customer.ai_opportunities = result.get("opportunities", [])
        customer.status = CustomerStatus.REPORTED.value
        log_activity(
            db, customer_id, "ai_analysis_completed",
            user_id=current_user.id
        )
        db.commit()
        db.refresh(customer)
        
        return AnalyzeResponse(
            success=True,
            message="分析完成",
            customer_id=customer_id,
            report=customer.ai_report,
            opportunities=customer.ai_opportunities
        )
        
    except Exception as e:
        # 分析失败，恢复状态
        customer.status = CustomerStatus.PENDING.value
        log_activity(
            db, customer_id, "ai_analysis_failed",
            {"error": str(e)},
            user_id=current_user.id
        )
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"AI 分析失败: {str(e)}"
        )


@router.post("/{customer_id}/stream")
async def analyze_customer_stream(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    触发 AI 分析 - 流式输出版本
    
    使用 Server-Sent Events (SSE) 实时返回分析结果
    """
    # 获取客户
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    if not customer.kyc_data:
        raise HTTPException(status_code=400, detail="客户尚未填写 KYC 表单")
    
    # 更新状态为分析中
    customer.status = CustomerStatus.ANALYZING.value
    user_id = current_user.id
    log_activity(
        db, customer_id, "ai_analysis_triggered",
        user_id=user_id
    )
    db.commit()

    # 保存客户数据用于流式处理
    kyc_data = customer.kyc_data
    related_contacts = customer.related_contacts
    
    async def generate_stream():
        """生成 SSE 流"""
        accumulated_content = ""
        
        try:
            async for chunk in analyze_customer_kyc_stream(
                kyc_data=kyc_data,
                related_contacts=related_contacts
            ):
                # 解析 chunk 以累积内容
                if chunk.startswith("data: "):
                    try:
                        data = json.loads(chunk[6:].strip())
                        if data.get("type") == "content":
                            accumulated_content += data.get("content", "")
                        elif data.get("type") == "done":
                            # 如果 done 事件包含完整内容，使用它
                            if data.get("full_content"):
                                accumulated_content = data.get("full_content")
                    except:
                        pass
                
                yield chunk
            
            # 流结束后，更新数据库
            # 重新获取数据库会话中的客户对象
            from app.database import SessionLocal
            with SessionLocal() as new_db:
                db_customer = new_db.query(Customer).filter(Customer.id == customer_id).first()
                if db_customer:
                    db_customer.ai_report = accumulated_content
                    db_customer.ai_opportunities = []
                    db_customer.status = CustomerStatus.REPORTED.value
                    log_activity(
                        new_db, customer_id, "ai_analysis_completed",
                        user_id=user_id
                    )
                    new_db.commit()
                    print(f"✅ 客户 {customer_id} 报告已保存，长度: {len(accumulated_content)}")
        
        except Exception as e:
            print(f"❌ 流式处理异常: {str(e)}")
            # 恢复客户状态
            from app.database import SessionLocal
            with SessionLocal() as new_db:
                db_customer = new_db.query(Customer).filter(Customer.id == customer_id).first()
                if db_customer:
                    db_customer.status = CustomerStatus.PENDING.value
                    log_activity(
                        new_db, customer_id, "ai_analysis_failed",
                        {"error": str(e)},
                        user_id=user_id
                    )
                    new_db.commit()
            
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )

