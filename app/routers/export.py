"""
数据导出 API 路由
"""
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.database import get_db
from app.models import Customer, FormTemplate, User
from app.services.auth_service import get_current_user

router = APIRouter()


@router.get("/customers")
def export_customers_csv(
    fields: str = Query("basic", description="导出字段: basic,kyc,ai_report"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    导出客户数据为 CSV 文件

    fields 参数用逗号分隔，支持：
    - basic: 基础信息（ID/姓名/状态/创建时间/跟进日期/生日/负责顾问）
    - kyc: KYC 表单数据（动态字段）
    - ai_report: AI 分析报告
    """
    field_set = {f.strip() for f in fields.split(",")}

    # 构建查询
    query = db.query(Customer).filter(Customer.is_deleted == 0)

    # 权限过滤
    if not current_user.is_admin:
        query = query.filter(
            or_(
                Customer.owner_user_id == current_user.id,
                Customer.owner_user_id.is_(None)
            )
        )

    if status:
        query = query.filter(Customer.status == status)

    customers = query.order_by(Customer.created_at.desc()).all()

    # 获取用户映射（用于顾问名称）
    users_map = {}
    if "basic" in field_set:
        all_users = db.query(User).all()
        users_map = {u.id: (u.display_name or u.username) for u in all_users}

    # 获取表单字段定义（用于 KYC 列）
    kyc_fields = []
    if "kyc" in field_set:
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
        if form_template and form_template.schema:
            schema = form_template.schema
            for section in schema.get("sections", []):
                for field in section.get("fields", []):
                    kyc_fields.append({
                        "name": field["name"],
                        "label": field.get("label", field["name"]),
                        "type": field.get("type", "text")
                    })

    # 构建 CSV 表头
    headers = []
    if "basic" in field_set:
        headers.extend(["ID", "姓名", "状态", "创建时间", "下次跟进", "生日", "负责顾问"])
    if "kyc" in field_set:
        headers.extend([f["label"] for f in kyc_fields])
    if "ai_report" in field_set:
        headers.append("AI分析报告")

    # 生成 CSV 内容
    def generate():
        output = io.StringIO()
        # 写入 UTF-8 BOM（确保 Excel 正确识别中文编码）
        yield '\ufeff'

        writer = csv.writer(output)
        writer.writerow(headers)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for customer in customers:
            row = []

            if "basic" in field_set:
                row.extend([
                    customer.id,
                    customer.name,
                    customer.status,
                    customer.created_at.strftime("%Y-%m-%d %H:%M") if customer.created_at else "",
                    customer.next_follow_up.strftime("%Y-%m-%d") if customer.next_follow_up else "",
                    customer.birthday.strftime("%Y-%m-%d") if customer.birthday else "",
                    users_map.get(customer.owner_user_id, "") if customer.owner_user_id else ""
                ])

            if "kyc" in field_set:
                kyc_data = customer.kyc_data or {}
                for field in kyc_fields:
                    value = kyc_data.get(field["name"], "")
                    # 多选值用顿号连接
                    if isinstance(value, list):
                        value = "、".join(str(v) for v in value)
                    row.append(value if value is not None else "")

            if "ai_report" in field_set:
                report = customer.ai_report or ""
                # 确保报告文本在 CSV 中不会出问题
                report = report.replace("\r\n", "\n").replace("\r", "\n")
                row.append(report)

            writer.writerow(row)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=customers_export.csv"
        }
    )
