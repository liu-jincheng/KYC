"""
AI 分析 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, CustomerStatus
from app.schemas import AnalyzeResponse
from app.services.coze_service import analyze_customer_kyc

router = APIRouter()


@router.post("/{customer_id}", response_model=AnalyzeResponse)
async def analyze_customer(
    customer_id: int,
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
        db.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"AI 分析失败: {str(e)}"
        )

