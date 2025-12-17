"""
FastAPI 应用入口
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import markdown

from app.config import settings
from app.database import init_db, get_db, SessionLocal
from app.models import Customer, FormTemplate, CustomerStatus
from app.routers import customers, forms, analyze, dashboard


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
    db = SessionLocal()
    try:
        # 获取统计数据
        total = db.query(Customer).count()
        stats = {
            "total": total,
            "pending": db.query(Customer).filter(Customer.status == CustomerStatus.PENDING.value).count(),
            "analyzing": db.query(Customer).filter(Customer.status == CustomerStatus.ANALYZING.value).count(),
            "reported": db.query(Customer).filter(Customer.status == CustomerStatus.REPORTED.value).count(),
            "following": db.query(Customer).filter(Customer.status == CustomerStatus.FOLLOWING.value).count(),
            "signed": db.query(Customer).filter(Customer.status == CustomerStatus.SIGNED.value).count(),
        }
        
        # 获取最近客户
        recent_customers = db.query(Customer).order_by(Customer.created_at.desc()).limit(5).all()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": stats,
            "recent_customers": recent_customers,
            "page_title": "仪表盘"
        })
    finally:
        db.close()


@app.get("/customers", response_class=HTMLResponse)
async def customer_list_page(request: Request, status: str = None):
    """客户列表页"""
    db = SessionLocal()
    try:
        query = db.query(Customer)
        if status:
            query = query.filter(Customer.status == status)
        customers_list = query.order_by(Customer.created_at.desc()).all()
        
        return templates.TemplateResponse("customer_list.html", {
            "request": request,
            "customers": customers_list,
            "current_status": status,
            "statuses": [s.value for s in CustomerStatus],
            "page_title": "客户列表"
        })
    finally:
        db.close()


@app.get("/customers/new", response_class=HTMLResponse)
async def customer_new_page(request: Request):
    """新建客户页"""
    db = SessionLocal()
    try:
        # 获取当前激活的表单配置
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
        
        return templates.TemplateResponse("customer_form.html", {
            "request": request,
            "form_schema": form_template.schema if form_template else None,
            "customer": None,
            "page_title": "新建客户"
        })
    finally:
        db.close()


@app.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail_page(request: Request, customer_id: int):
    """客户详情页"""
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "message": "客户不存在",
                "page_title": "错误"
            })
        
        # 获取表单配置用于显示标签
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
        
        return templates.TemplateResponse("customer_detail.html", {
            "request": request,
            "customer": customer,
            "form_schema": form_template.schema if form_template else None,
            "statuses": [s.value for s in CustomerStatus],
            "page_title": f"客户详情 - {customer.name}"
        })
    finally:
        db.close()


@app.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
async def customer_edit_page(request: Request, customer_id: int):
    """编辑客户页"""
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "message": "客户不存在",
                "page_title": "错误"
            })
        
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
        
        return templates.TemplateResponse("customer_form.html", {
            "request": request,
            "form_schema": form_template.schema if form_template else None,
            "customer": customer,
            "page_title": f"编辑客户 - {customer.name}"
        })
    finally:
        db.close()


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """表单配置页"""
    db = SessionLocal()
    try:
        form_template = db.query(FormTemplate).filter(FormTemplate.is_active == 1).first()
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "form_template": form_template,
            "page_title": "表单设置"
        })
    finally:
        db.close()


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """使用说明页"""
    return templates.TemplateResponse("help.html", {
        "request": request,
        "page_title": "使用说明"
    })
