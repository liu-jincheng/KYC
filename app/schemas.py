"""
Pydantic 数据验证模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import date as dt_date, datetime
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
    next_follow_up: Optional[dt_date] = Field(default=None, description="下次跟进日期")
    birthday: Optional[dt_date] = Field(default=None, description="生日")
    owner_user_id: Optional[int] = Field(default=None, description="归属顾问用户ID")


class CustomerUpdate(BaseModel):
    """更新客户请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    kyc_data: Optional[dict] = None
    related_contacts: Optional[List[dict]] = None
    next_follow_up: Optional[dt_date] = None
    birthday: Optional[dt_date] = None
    owner_user_id: Optional[int] = None


class CustomerStatusUpdate(BaseModel):
    """更新客户状态请求"""
    status: CustomerStatusEnum


class CustomerBirthdayUpdate(BaseModel):
    """更新客户生日请求"""
    birthday: Optional[dt_date] = None


class CustomerResponse(BaseModel):
    """客户响应"""
    id: int
    name: str
    kyc_data: Optional[dict] = None
    status: str
    ai_report: Optional[str] = None
    ai_opportunities: Optional[List[dict]] = None
    birthday: Optional[dt_date] = None
    related_contacts: Optional[List[dict]] = None
    next_follow_up: Optional[dt_date] = None
    owner_user_id: Optional[int] = None
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
    date: Optional[dt_date] = None


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


# ============ 表单邀请相关 Schema ============

class InviteCreate(BaseModel):
    """创建邀请链接请求"""
    customer_id: int = Field(..., description="客户ID")
    expires_days: Optional[int] = Field(default=7, description="过期天数，默认7天")


class InviteResponse(BaseModel):
    """邀请链接响应"""
    id: int
    customer_id: int
    token: str
    expires_at: Optional[datetime] = None
    is_active: int
    used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    invite_url: Optional[str] = None  # 完整的邀请链接

    class Config:
        from_attributes = True


class InviteFormData(BaseModel):
    """客户提交的表单数据"""
    kyc_data: dict = Field(..., description="KYC表单数据")


class InviteValidateResponse(BaseModel):
    """验证邀请链接响应"""
    valid: bool
    message: str
    customer_name: Optional[str] = None
    form_schema: Optional[dict] = None


# ============ 用户与权限相关 Schema ============

class UserRoleEnum(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    display_name: Optional[str] = Field(None, max_length=100, description="显示名称")
    role: UserRoleEnum = Field(default=UserRoleEnum.USER, description="角色")


class UserUpdate(BaseModel):
    """更新用户请求"""
    display_name: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRoleEnum] = None
    is_active: Optional[int] = None


class UserPasswordUpdate(BaseModel):
    """更新用户密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    display_name: Optional[str] = None
    role: str
    is_active: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    message: str
    user: Optional[UserResponse] = None

