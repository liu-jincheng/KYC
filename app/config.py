"""
配置管理模块
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """应用配置"""
    # 应用信息
    APP_NAME: str = "侨慧·本地CRM"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./data/crm.db"
    
    # Coze OAuth 2.0 配置
    COZE_CLIENT_ID: str = ""
    COZE_CLIENT_SECRET: str = ""
    COZE_WORKFLOW_ID: str = ""
    COZE_BIRTHDAY_WORKFLOW_ID: str = ""  # 生日祝福工作流 ID
    COZE_API_BASE_URL: str = "https://api.coze.cn/v1"  # Workflow API 基础 URL
    COZE_AUTH_API_BASE_URL: str = "https://api.coze.cn"  # OAuth Token 接口 (无 /v1 前缀)
    COZE_WWW_BASE_URL: str = "https://www.coze.cn"  # 授权页面域名
    
    @property
    def COZE_REDIRECT_URI(self) -> str:
        """根据 DEBUG 模式自动选择回调地址"""
        if self.DEBUG:
            return "http://127.0.0.1:8000/callback"
        return "http://115.190.197.29/callback"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取缓存的配置实例"""
    return Settings()


settings = get_settings()

