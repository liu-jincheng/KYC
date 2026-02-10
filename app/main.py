"""
FastAPI 应用入口
"""
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
from typing import Optional
import math
import markdown

from app.config import settings
from app.database import init_db, get_db, SessionLocal
from app.models import Customer, FormTemplate, CustomerStatus, FormInvite, User
from app.routers import customers, forms, analyze, dashboard, ai, invites, auth, coze_auth, activity, export
from app.services.auth_service import get_current_user_from_request, check_customer_access


def require_login(request: Request):
    """页面路由登录检查，未登录则重定向到登录页"""
    current_user = get_current_user_from_request(request)
    if not current_user:
        return None, RedirectResponse(url="/login", status_code=302)
    return current_user, None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    print(f"🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    init_db()
    yield
    # 关闭时清理资源
    print("👋 应用关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 配置模板引擎
templates = Jinja2Templates(directory="app/templates")

# 注册 API 路由
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(forms.router, prefix="/api/forms", tags=["forms"])
app.include_router(analyze.router, prefix="/api/analyze", tags=["analyze"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(invites.router, prefix="/api/invites", tags=["invites"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(coze_auth.router, tags=["coze_auth"])
app.include_router(activity.router, prefix="/api/activity", tags=["activity"])
app.include_router(export.router, prefix="/api/export", tags=["export"])


# Jinja2 自定义过滤器
def markdown_filter(text: str) -> str:
    """将 Markdown 转换为 HTML"""
    if not text:
        return ""
    return markdown.markdown(text, extensions=['tables', 'fenced_code'])


templates.env.filters['markdown'] = markdown_filter


# ============ 页面路由 ============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页仪表盘"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        from sqlalchemy import or_, func

        # 基础查询：排除已删除
        base_query = db.query(Customer).filter(Customer.is_deleted == 0)
        if not current_user.is_admin:
            base_query = base_query.filter(
                or_(
                    Customer.owner_user_id == current_user.id,
                    Customer.owner_user_id.is_(None)
                )
            )

        # 使用 GROUP BY 优化统计查询
        status_counts = (
            base_query
            .with_entities(Customer.status, func.count(Customer.id))
            .group_by(Customer.status)
            .all()
        )
        counts = dict(status_counts)
        total = sum(counts.values())

        stats = {
            "total": total,
            "pending": counts.get(CustomerStatus.PENDING.value, 0),
            "analyzing": counts.get(CustomerStatus.ANALYZING.value, 0),
            "reported": counts.get(CustomerStatus.REPORTED.value, 0),
            "following": counts.get(CustomerStatus.FOLLOWING.value, 0),
            "signed": counts.get(CustomerStatus.SIGNED.value, 0),
        }

        # 获取最近客户
        recent_customers = (
            base_query
            .order_by(Customer.created_at.desc())
            .limit(5)
            .all()
        )

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": current_user,
            "stats": stats,
            "recent_customers": recent_customers,
            "page_title": "仪表盘"
        })
    finally:
        db.close()


@app.get("/customers", response_class=HTMLResponse)
async def customer_list_page(
    request: Request,
    status: str = None,
    search: str = None,
    owner_id: Optional[int] = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
    page_size: int = 20
):
    """客户列表页"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        from sqlalchemy import or_
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

        if search:
            query = query.filter(Customer.name.ilike(f"%{search}%"))

        if owner_id is not None:
            if owner_id == 0:
                query = query.filter(Customer.owner_user_id.is_(None))
            else:
                query = query.filter(Customer.owner_user_id == owner_id)

        if date_from:
            try:
                from datetime import datetime
                d = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(Customer.created_at >= d)
            except ValueError:
                pass

        if date_to:
            try:
                from datetime import datetime, timedelta
                d = datetime.strptime(date_to, "%Y-%m-%d")
                query = query.filter(Customer.created_at < d + timedelta(days=1))
            except ValueError:
                pass

        total = query.count()
        total_pages = max(1, math.ceil(total / page_size))
        skip = (page - 1) * page_size
        customers_list = query.order_by(Customer.created_at.desc()).offset(skip).limit(page_size).all()

        # 用户映射（用于看板视图显示顾问名称）
        all_users = db.query(User).all()
        users_map = {u.id: (u.display_name or u.username) for u in all_users}

        return templates.TemplateResponse("customer_list.html", {
            "request": request,
            "current_user": current_user,
            "customers": customers_list,
            "current_status": status,
            "statuses": [s.value for s in CustomerStatus],
            "users_map": users_map,
            "page_title": "客户列表",
            # 分页相关
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            # 筛选条件回传
            "search": search or "",
            "owner_id": owner_id,
            "date_from": date_from or "",
            "date_to": date_to or "",
        })
    finally:
        db.close()


@app.get("/customers/new", response_class=HTMLResponse)
async def customer_new_page(request: Request):
    """新建客户页"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        # 获取当前激活的表单配置
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()

        # 如果是管理员，获取所有用户列表（用于分配客户归属）
        users_list = []
        if current_user.is_admin:
            users_list = db.query(User).filter(User.is_active == 1).all()

        return templates.TemplateResponse("customer_form.html", {
            "request": request,
            "current_user": current_user,
            "form_schema": form_template.schema if form_template else None,
            "customer": None,
            "users_list": users_list,
            "page_title": "新建客户"
        })
    finally:
        db.close()


@app.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail_page(request: Request, customer_id: int):
    """客户详情页"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == 0
        ).first()
        if not customer:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "current_user": current_user,
                "message": "客户不存在",
                "page_title": "错误"
            })

        # 权限检查
        if not check_customer_access(customer.owner_user_id, current_user):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "current_user": current_user,
                "message": "无权访问此客户",
                "page_title": "权限不足"
            })

        # 获取表单配置用于显示标签
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()

        # 获取客户归属用户信息
        owner_user = None
        if customer.owner_user_id:
            owner_user = db.query(User).filter(User.id == customer.owner_user_id).first()

        return templates.TemplateResponse("customer_detail.html", {
            "request": request,
            "current_user": current_user,
            "customer": customer,
            "owner_user": owner_user,
            "form_schema": form_template.schema if form_template else None,
            "statuses": [s.value for s in CustomerStatus],
            "page_title": f"客户详情 - {customer.name}"
        })
    finally:
        db.close()


@app.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
async def customer_edit_page(request: Request, customer_id: int):
    """编辑客户页"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == 0
        ).first()
        if not customer:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "current_user": current_user,
                "message": "客户不存在",
                "page_title": "错误"
            })

        # 权限检查
        if not check_customer_access(customer.owner_user_id, current_user):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "current_user": current_user,
                "message": "无权编辑此客户",
                "page_title": "权限不足"
            })

        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()

        # 如果是管理员，获取所有用户列表（用于分配客户归属）
        users_list = []
        if current_user.is_admin:
            users_list = db.query(User).filter(User.is_active == 1).all()

        return templates.TemplateResponse("customer_form.html", {
            "request": request,
            "current_user": current_user,
            "form_schema": form_template.schema if form_template else None,
            "customer": customer,
            "users_list": users_list,
            "page_title": f"编辑客户 - {customer.name}"
        })
    finally:
        db.close()


@app.get("/recycle-bin", response_class=HTMLResponse)
async def recycle_bin_page(
    request: Request,
    page: int = 1,
    page_size: int = 20
):
    """回收站页面"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        from sqlalchemy import or_
        query = db.query(Customer).filter(Customer.is_deleted == 1)

        # 权限过滤
        if not current_user.is_admin:
            query = query.filter(
                or_(
                    Customer.owner_user_id == current_user.id,
                    Customer.owner_user_id.is_(None)
                )
            )

        total = query.count()
        total_pages = max(1, math.ceil(total / page_size))
        skip = (page - 1) * page_size
        customers_list = query.order_by(Customer.deleted_at.desc()).offset(skip).limit(page_size).all()

        # 用户映射
        all_users = db.query(User).all()
        users_map = {u.id: (u.display_name or u.username) for u in all_users}

        return templates.TemplateResponse("recycle_bin.html", {
            "request": request,
            "current_user": current_user,
            "customers": customers_list,
            "users_map": users_map,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "page_title": "回收站"
        })
    finally:
        db.close()


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """表单配置页"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()

        is_admin = current_user.is_admin

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "current_user": current_user,
            "form_template": form_template,
            "is_admin": is_admin,
            "page_title": "表单设置"
        })
    finally:
        db.close()


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """使用说明页"""
    current_user = get_current_user_from_request(request)
    return templates.TemplateResponse("help.html", {
        "request": request,
        "current_user": current_user,
        "page_title": "使用说明"
    })


# ============ 用户认证页面路由 ============

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页"""
    # 如果已登录，重定向到首页
    current_user = get_current_user_from_request(request)
    if current_user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "page_title": "登录"
    })


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """用户管理页（管理员）"""
    current_user, redirect = require_login(request)
    if redirect:
        return redirect

    if not current_user.is_admin:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "current_user": current_user,
            "message": "需要管理员权限",
            "page_title": "权限不足"
        })

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()

        return templates.TemplateResponse("admin_users.html", {
            "request": request,
            "current_user": current_user,
            "users": users,
            "page_title": "用户管理"
        })
    finally:
        db.close()


# ============ 外部填写页面路由 ============

@app.get("/fill/{token}", response_class=HTMLResponse)
async def external_fill_page(request: Request, token: str):
    """
    外部客户填写页面

    通过邀请链接访问的公开表单页面
    """
    from datetime import datetime

    db = SessionLocal()
    try:
        # 查找邀请记录
        invite = db.query(FormInvite).filter(FormInvite.token == token).first()

        # 验证邀请有效性
        error_message = None
        customer_name = None
        form_schema = None

        if not invite:
            error_message = "邀请链接无效，请联系您的顾问获取正确的链接。"
        elif invite.used_at is not None:
            error_message = "该链接已被使用。如需重新填写，请联系您的顾问。"
        elif invite.expires_at and invite.expires_at < datetime.now():
            error_message = "邀请链接已过期。请联系您的顾问获取新的链接。"
        elif invite.is_active != 1:
            error_message = "邀请链接已失效。请联系您的顾问。"
        else:
            # 获取客户信息
            customer = db.query(Customer).filter(Customer.id == invite.customer_id).first()
            if not customer:
                error_message = "关联的客户记录不存在。"
            else:
                customer_name = customer.name
                # 获取当前激活的表单配置
                form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
                form_schema = form_template.schema if form_template else None

        if error_message:
            return templates.TemplateResponse("fill_form.html", {
                "request": request,
                "error_message": error_message,
                "token": token,
                "customer_name": None,
                "form_schema": None,
                "page_title": "表单填写"
            })

        return templates.TemplateResponse("fill_form.html", {
            "request": request,
            "error_message": None,
            "token": token,
            "customer_name": customer_name,
            "form_schema": form_schema,
            "page_title": f"填写 KYC 信息 - {customer_name}"
        })
    finally:
        db.close()


@app.get("/fill/{token}/success", response_class=HTMLResponse)
async def external_fill_success_page(request: Request, token: str):
    """外部填写成功页面"""
    return templates.TemplateResponse("fill_success.html", {
        "request": request,
        "page_title": "提交成功"
    })
