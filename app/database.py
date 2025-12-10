"""
数据库初始化模块
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
import os

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 需要此参数
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


def get_db():
    """
    数据库会话依赖项
    用于 FastAPI 的依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库
    创建所有表并初始化默认数据
    """
    from app.models import Base, FormTemplate, DEFAULT_FORM_SCHEMA
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    # 初始化默认表单配置
    db = SessionLocal()
    try:
        # 检查是否已存在默认表单
        existing = db.query(FormTemplate).filter(FormTemplate.version == "1.0").first()
        if not existing:
            default_form = FormTemplate(
                version="1.0",
                name="KYC 标准表单",
                schema=DEFAULT_FORM_SCHEMA,
                is_active=1
            )
            db.add(default_form)
            db.commit()
            print("✅ 默认表单配置已初始化")
        else:
            print("ℹ️ 默认表单配置已存在")
    finally:
        db.close()

