"""
表单引擎服务
"""
from typing import Any, Dict, List, Optional
from app.models import DEFAULT_FORM_SCHEMA


def get_field_label(schema: dict, field_name: str) -> str:
    """
    根据字段名获取标签
    
    Args:
        schema: 表单配置
        field_name: 字段名
    
    Returns:
        字段标签，如果找不到则返回字段名
    """
    for section in schema.get("sections", []):
        for field in section.get("fields", []):
            if field.get("name") == field_name:
                return field.get("label", field_name)
    return field_name


def get_field_options(schema: dict, field_name: str) -> List[str]:
    """
    获取字段的选项列表
    
    Args:
        schema: 表单配置
        field_name: 字段名
    
    Returns:
        选项列表
    """
    for section in schema.get("sections", []):
        for field in section.get("fields", []):
            if field.get("name") == field_name:
                return field.get("options", [])
    return []


def format_kyc_value(schema: dict, field_name: str, value: Any) -> str:
    """
    格式化 KYC 字段值用于显示
    
    Args:
        schema: 表单配置
        field_name: 字段名
        value: 字段值
    
    Returns:
        格式化后的显示文本
    """
    if value is None:
        return "-"
    
    if isinstance(value, list):
        return "、".join(str(v) for v in value) if value else "-"
    
    return str(value)


def validate_kyc_data(schema: dict, data: dict) -> tuple[bool, List[str]]:
    """
    验证 KYC 数据是否符合表单配置
    
    Args:
        schema: 表单配置
        data: KYC 数据
    
    Returns:
        (是否有效, 错误消息列表)
    """
    errors = []
    
    for section in schema.get("sections", []):
        for field in section.get("fields", []):
            field_name = field.get("name")
            field_label = field.get("label", field_name)
            required = field.get("required", False)
            field_type = field.get("type")
            options = field.get("options", [])
            max_select = field.get("max")
            
            value = data.get(field_name)
            
            # 检查必填字段
            if required and (value is None or value == "" or value == []):
                errors.append(f"{field_label} 为必填项")
                continue
            
            if value is None or value == "" or value == []:
                continue
            
            # 检查选项类型字段的值是否在选项列表中
            if field_type == "select" and options:
                if value not in options:
                    errors.append(f"{field_label} 的值不在可选项中")
            
            # 检查多选字段
            if field_type == "multiselect":
                if not isinstance(value, list):
                    errors.append(f"{field_label} 应为列表类型")
                else:
                    if options:
                        invalid = [v for v in value if v not in options]
                        if invalid:
                            errors.append(f"{field_label} 包含无效选项: {', '.join(invalid)}")
                    if max_select and len(value) > max_select:
                        errors.append(f"{field_label} 最多选择 {max_select} 项")
            
            # 检查数字类型
            if field_type == "number" and value is not None:
                try:
                    int(value)
                except (ValueError, TypeError):
                    errors.append(f"{field_label} 应为数字")
    
    return len(errors) == 0, errors


def get_section_fields(schema: dict, section_title: str) -> List[dict]:
    """
    获取指定分组的所有字段
    
    Args:
        schema: 表单配置
        section_title: 分组标题
    
    Returns:
        字段列表
    """
    for section in schema.get("sections", []):
        if section.get("title") == section_title:
            return section.get("fields", [])
    return []

