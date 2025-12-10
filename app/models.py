"""
数据库模型定义
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, JSON
from sqlalchemy.sql import func
from app.database import Base
import enum


class CustomerStatus(str, enum.Enum):
    """客户状态枚举"""
    PENDING = "待录入"
    ANALYZING = "AI分析中"
    REPORTED = "已出方案"
    FOLLOWING = "跟进中"
    SIGNED = "已签约"


class FormTemplate(Base):
    """
    表单配置表 - 存储KYC表单结构定义
    """
    __tablename__ = "form_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(20), unique=True, nullable=False)  # 版本号
    name = Column(String(100), nullable=False)                  # 表单名称
    schema = Column(JSON, nullable=False)                       # 表单结构定义
    is_active = Column(Integer, default=1)                      # 是否激活
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Customer(Base):
    """
    客户表 - 存储客户信息和AI分析结果
    """
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)                  # 客户姓名
    kyc_data = Column(JSON, nullable=True)                      # KYC表单原始数据
    status = Column(String(20), default=CustomerStatus.PENDING.value)  # 状态
    ai_report = Column(Text, nullable=True)                     # AI分析报告(Markdown)
    ai_opportunities = Column(JSON, nullable=True)              # AI商机挖掘结果
    
    # [预留字段] 用于存储客户生日，MVP阶段默认为空
    # 后续可通过接口更新，用于生日提醒功能
    birthday = Column(Date, nullable=True)
    
    related_contacts = Column(JSON, nullable=True)              # 关联人信息
    next_follow_up = Column(Date, nullable=True)                # 下次跟进日期
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


# 默认表单配置结构
DEFAULT_FORM_SCHEMA = {
    "version": "1.0",
    "sections": [
        {
            "title": "客户来源",
            "fields": [
                {
                    "name": "source",
                    "label": "客户来源",
                    "type": "select",
                    "options": ["朋友推荐", "网络搜索", "社交媒体", "线下活动", "其他"],
                    "required": False
                }
            ]
        },
        {
            "title": "基本信息",
            "fields": [
                {"name": "name", "label": "姓名", "type": "text", "required": True},
                {"name": "city", "label": "所在城市", "type": "text", "required": False},
                {
                    "name": "age_group",
                    "label": "年龄段",
                    "type": "select",
                    "options": ["18-35", "36-45", "46-55", "56-65", "65+"],
                    "required": False
                },
                {
                    "name": "education",
                    "label": "学历",
                    "type": "select",
                    "options": ["高中及以下", "本科", "硕士", "博士", "其他"],
                    "required": False
                }
            ]
        },
        {
            "title": "家庭结构",
            "fields": [
                {"name": "children_count", "label": "子女数量", "type": "number", "required": False},
                {
                    "name": "children_education",
                    "label": "子女教育阶段",
                    "type": "multiselect",
                    "options": ["学龄前", "小学", "初中", "高中", "本科", "研究生", "已工作"],
                    "required": False
                }
            ]
        },
        {
            "title": "资产与职业",
            "fields": [
                {
                    "name": "asset_level",
                    "label": "资产级别",
                    "type": "select",
                    "options": ["A8 (百万级)", "A9 (千万级)", "A10 (亿级)", "A11 (十亿级)"],
                    "required": False
                },
                {
                    "name": "job_type",
                    "label": "职业类型",
                    "type": "select",
                    "options": ["企业主", "高管", "专业人士", "投资人", "自由职业", "其他"],
                    "required": False
                },
                {"name": "job_title", "label": "职位/职称", "type": "text", "required": False}
            ]
        },
        {
            "title": "核心诉求",
            "fields": [
                {
                    "name": "core_needs",
                    "label": "核心诉求(最多3项)",
                    "type": "multiselect",
                    "max": 3,
                    "options": ["资产配置", "子女教育", "风险规避", "税务优化", "养老规划", "身份备份", "商业拓展"],
                    "required": False
                }
            ]
        },
        {
            "title": "意向国家",
            "fields": [
                {
                    "name": "target_countries",
                    "label": "意向国家",
                    "type": "multiselect",
                    "options": ["新加坡", "土耳其", "中国香港", "美国", "加拿大", "英国", "葡萄牙", "马耳他", "希腊", "其他"],
                    "required": False
                }
            ]
        },
        {
            "title": "办理周期",
            "fields": [
                {
                    "name": "timeline",
                    "label": "期望办理周期",
                    "type": "select",
                    "options": ["6个月内", "6-12个月", "1-2年", "不着急"],
                    "required": False
                }
            ]
        },
        {
            "title": "补充信息",
            "fields": [
                {"name": "notes", "label": "其他补充", "type": "textarea", "required": False}
            ]
        }
    ]
}

