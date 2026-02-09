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
    from app.models import Base, FormTemplate, DEFAULT_FORM_SCHEMA, User, UserRole
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    # ========== 数据库迁移：为旧表添加新列 ==========
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # 检查并添加 customers.owner_user_id 列
        try:
            db.execute(text("SELECT owner_user_id FROM customers LIMIT 1"))
        except Exception:
            print("📦 迁移：为 customers 表添加 owner_user_id 列...")
            db.execute(text("ALTER TABLE customers ADD COLUMN owner_user_id INTEGER"))
            db.commit()
            print("✅ 迁移完成")

        # 检查并添加 customers.is_deleted 列（软删除）
        try:
            db.execute(text("SELECT is_deleted FROM customers LIMIT 1"))
        except Exception:
            print("📦 迁移：为 customers 表添加 is_deleted 列...")
            db.execute(text("ALTER TABLE customers ADD COLUMN is_deleted INTEGER DEFAULT 0"))
            db.commit()
            print("✅ is_deleted 列添加完成")

        # 检查并添加 customers.deleted_at 列
        try:
            db.execute(text("SELECT deleted_at FROM customers LIMIT 1"))
        except Exception:
            print("📦 迁移：为 customers 表添加 deleted_at 列...")
            db.execute(text("ALTER TABLE customers ADD COLUMN deleted_at DATETIME"))
            db.commit()
            print("✅ deleted_at 列添加完成")

        # 创建索引（如不存在）
        index_statements = [
            "CREATE INDEX IF NOT EXISTS ix_customers_status ON customers(status)",
            "CREATE INDEX IF NOT EXISTS ix_customers_name ON customers(name)",
            "CREATE INDEX IF NOT EXISTS ix_customers_birthday ON customers(birthday)",
            "CREATE INDEX IF NOT EXISTS ix_customers_next_follow_up ON customers(next_follow_up)",
            "CREATE INDEX IF NOT EXISTS ix_customers_is_deleted ON customers(is_deleted)",
        ]
        for stmt in index_statements:
            try:
                db.execute(text(stmt))
            except Exception:
                pass
        db.commit()
        print("✅ 索引检查完成")
    except Exception as e:
        print(f"⚠️ 迁移检查时出错: {e}")
        db.rollback()
    finally:
        db.close()
    
    db = SessionLocal()
    try:
        # ========== 初始化或升级表单配置 ==========
        current_version = DEFAULT_FORM_SCHEMA.get("version", "1.0")
        
        # 检查最新版本是否已存在
        existing_latest = db.query(FormTemplate).filter(FormTemplate.version == current_version).first()
        
        if not existing_latest:
            # 将所有旧版本设为非激活
            db.query(FormTemplate).update({FormTemplate.is_active: 0})
            
            # 创建新版本
            new_form = FormTemplate(
                version=current_version,
                name="KYC 标准表单",
                schema=DEFAULT_FORM_SCHEMA,
                is_active=1
            )
            db.add(new_form)
            db.commit()
            print(f"✅ 表单配置已升级到 v{current_version}")
        else:
            # 确保最新版本是激活状态
            if existing_latest.is_active != 1:
                db.query(FormTemplate).update({FormTemplate.is_active: 0})
                existing_latest.is_active = 1
                db.commit()
            print(f"ℹ️ 表单配置 v{current_version} 已存在")
        
        # ========== 初始化默认管理员账户 ==========
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                password_hash=User.hash_password("admin123"),  # 默认密码
                display_name="系统管理员",
                role=UserRole.ADMIN.value,
                is_active=1
            )
            db.add(admin_user)
            db.commit()
            print("✅ 默认管理员账户已创建 (用户名: admin, 密码: admin123)")
        else:
            print("ℹ️ 管理员账户已存在")

        # ========== 初始化默认体验账户 ==========
        demo_user = db.query(User).filter(User.username == "demo").first()
        if not demo_user:
            demo_user = User(
                username="demo",
                password_hash=User.hash_password("demo123"),
                display_name="体验用户",
                role=UserRole.USER.value,
                is_active=1
            )
            db.add(demo_user)
            db.commit()
            print("✅ 默认体验账户已创建 (用户名: demo, 密码: demo123)")
        else:
            print("ℹ️ 体验账户已存在")
            
    finally:
        db.close()

