"""
Pydantic 数据验证模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import date, datetime
from enum import Enum


class CustomerStatusEnum(str, Enum):
    """客户状态枚举"""
    PENDING = "待录入"
    ANALYZING = "AI分析中"
    REPORTED = "已出方案"
    FOLLOWING = "跟进中"
    SIGNED = "已签约"


# ============ 客户相关 Schema ============

class CustomerCreate(BaseModel):
    """创建客户请求"""
    name: str = Field(..., min_length=1, max_length=100, description="客户姓名")
    kyc_data: Optional[dict] = Field(default=None, description="KYC表单数据")
    related_contacts: Optional[List[dict]] = Field(default=None, description="关联人信息")
    next_follow_up: Optional[date] = Field(default=None, description="下次跟进日期")


class CustomerUpdate(BaseModel):
    """更新客户请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    kyc_data: Optional[dict] = None
    related_contacts: Optional[List[dict]] = None
    next_follow_up: Optional[date] = None


class CustomerStatusUpdate(BaseModel):
    """更新客户状态请求"""
    status: CustomerStatusEnum


class CustomerBirthdayUpdate(BaseModel):
    """更新客户生日请求"""
    birthday: Optional[date] = None


class CustomerResponse(BaseModel):
    """客户响应"""
    id: int
    name: str
    kyc_data: Optional[dict] = None
    status: str
    ai_report: Optional[str] = None
    ai_opportunities: Optional[List[dict]] = None
    birthday: Optional[date] = None
    related_contacts: Optional[List[dict]] = None
    next_follow_up: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """客户列表响应"""
    total: int
    items: List[CustomerResponse]


# ============ 表单配置相关 Schema ============

class FormFieldSchema(BaseModel):
    """表单字段定义"""
    name: str
    label: str
    type: str  # text, select, multiselect, number, textarea
    options: Optional[List[str]] = None
    required: bool = False
    max: Optional[int] = None  # 用于 multiselect 限制选择数量


class FormSectionSchema(BaseModel):
    """表单分组定义"""
    title: str
    fields: List[FormFieldSchema]


class FormSchemaContent(BaseModel):
    """表单结构内容"""
    version: str
    sections: List[FormSectionSchema]


class FormTemplateResponse(BaseModel):
    """表单配置响应"""
    id: int
    version: str
    name: str
    schema: dict
    is_active: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FormTemplateUpdate(BaseModel):
    """更新表单配置请求"""
    name: Optional[str] = None
    schema: Optional[dict] = None


# ============ AI 分析相关 Schema ============

class AIOpportunity(BaseModel):
    """AI商机"""
    type: str
    description: str
    priority: str  # high, medium, low


class AIAnalysisResult(BaseModel):
    """AI分析结果"""
    report: str  # Markdown格式报告
    opportunities: List[AIOpportunity]


class AnalyzeResponse(BaseModel):
    """分析接口响应"""
    success: bool
    message: str
    customer_id: int
    report: Optional[str] = None
    opportunities: Optional[List[AIOpportunity]] = None


# ============ 仪表盘相关 Schema ============

class ReminderItem(BaseModel):
    """提醒项目"""
    type: str  # follow_up, birthday, stale
    customer_id: int
    customer_name: str
    message: str
    date: Optional[date] = None


class DashboardStats(BaseModel):
    """仪表盘统计"""
    total_customers: int
    pending_count: int
    analyzing_count: int
    reported_count: int
    following_count: int
    signed_count: int


class DashboardReminders(BaseModel):
    """仪表盘提醒"""
    follow_ups: List[ReminderItem]
    birthdays: List[ReminderItem]
    stale_analyses: List[ReminderItem]

