"""
表单配置 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FormTemplate
from app.schemas import FormTemplateResponse, FormTemplateUpdate

router = APIRouter()


@router.get("/active", response_model=FormTemplateResponse)
def get_active_form(db: Session = Depends(get_db)):
    """获取当前激活的表单配置"""
    form = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
    
    if not form:
        raise HTTPException(status_code=404, detail="未找到激活的表单配置")
    
    return FormTemplateResponse.model_validate(form)


@router.get("/{form_id}", response_model=FormTemplateResponse)
def get_form(form_id: int, db: Session = Depends(get_db)):
    """获取指定表单配置"""
    form = db.query(FormTemplate).filter(FormTemplate.id == form_id).first()
    
    if not form:
        raise HTTPException(status_code=404, detail="表单配置不存在")
    
    return FormTemplateResponse.model_validate(form)


@router.put("/{form_id}", response_model=FormTemplateResponse)
def update_form(
    form_id: int,
    form_data: FormTemplateUpdate,
    db: Session = Depends(get_db)
):
    """更新表单配置"""
    form = db.query(FormTemplate).filter(FormTemplate.id == form_id).first()
    
    if not form:
        raise HTTPException(status_code=404, detail="表单配置不存在")
    
    # 更新非空字段
    if form_data.name is not None:
        form.name = form_data.name
    if form_data.schema is not None:
        form.schema = form_data.schema
    
    db.commit()
    db.refresh(form)
    
    return FormTemplateResponse.model_validate(form)

