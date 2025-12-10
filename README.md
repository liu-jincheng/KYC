# 侨慧·本地CRM (QiaoHui Local CRM)

> 本地优先的高净值移民客户管理系统，为顾问提供安全、智能的客户管理体验。

## ✨ 核心特性

- **🔒 隐私安全** - 客户核心数据本地化存储（SQLite），无需担心云端数据泄露
- **🤖 AI 赋能** - 集成 Coze 云端工作流，智能生成移民方案建议
- **👨‍👩‍👧‍👦 关系挖掘** - 基于家庭结构和关联人信息，自动挖掘二次商机
- **📋 动态表单** - 可配置的 KYC 表单引擎，灵活适应业务需求
- **🔔 智能提醒** - 跟进提醒、生日祝福、状态滞留预警

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python) |
| 数据库 | SQLite + SQLAlchemy |
| 前端模板 | Jinja2 + Bootstrap 5 |
| AI 集成 | Coze Workflow API |

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- pip 或 poetry

### 2. 安装依赖

```bash
# 克隆项目
cd KYC

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量（可选）

创建 `.env` 文件配置 Coze API：

```env
# Coze API 配置（可选，不配置则使用模拟数据）
COZE_API_KEY=your_api_key_here
COZE_WORKFLOW_ID=your_workflow_id_here
```

### 4. 启动应用

```bash
python run.py
```

应用将在 http://127.0.0.1:8000 启动。

首次启动会自动：
- 创建 `data/crm.db` 数据库文件
- 初始化默认 KYC 表单配置

## 📁 项目结构

```
KYC/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库初始化
│   ├── models.py            # 数据模型
│   ├── schemas.py           # Pydantic 模型
│   ├── routers/             # API 路由
│   │   ├── customers.py     # 客户管理
│   │   ├── forms.py         # 表单配置
│   │   ├── analyze.py       # AI 分析
│   │   └── dashboard.py     # 仪表盘
│   ├── services/            # 业务服务
│   │   ├── coze_service.py  # Coze 集成
│   │   ├── reminder_service.py
│   │   └── form_service.py
│   ├── templates/           # Jinja2 模板
│   └── static/              # 静态资源
├── data/
│   └── crm.db               # SQLite 数据库
├── requirements.txt
├── run.py
└── README.md
```

## 📚 API 文档

启动应用后访问：

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 主要 API 端点

| 方法 | 路由 | 功能 |
|------|------|------|
| GET | `/api/customers` | 获取客户列表 |
| POST | `/api/customers` | 创建客户 |
| GET | `/api/customers/{id}` | 获取客户详情 |
| PUT | `/api/customers/{id}` | 更新客户 |
| PUT | `/api/customers/{id}/status` | 更新状态 |
| PUT | `/api/customers/{id}/birthday` | 更新生日 |
| POST | `/api/analyze/{id}` | AI 分析 |
| GET | `/api/dashboard/reminders` | 获取提醒 |
| GET | `/api/forms/active` | 获取表单配置 |

## 🎯 客户状态流转

```
待录入 → AI分析中 → 已出方案 → 跟进中 → 已签约
```

## 🔧 Coze 工作流配置

如需使用真实 AI 分析功能，请在 [Coze 平台](https://www.coze.cn) 创建工作流，并配置以下输入参数：

- `client_profile` - 客户基本信息
- `family_structure` - 家庭结构
- `needs_and_preferences` - 需求偏好
- `related_contacts` - 关联人信息

工作流应返回：

```json
{
  "report": "Markdown 格式的分析报告",
  "opportunities": [
    {"type": "商机类型", "description": "描述", "priority": "high/medium/low"}
  ]
}
```

## 📝 默认 KYC 表单字段

| 分组 | 字段 |
|------|------|
| 客户来源 | 来源渠道（朋友推荐/网络搜索/社交媒体/线下活动/其他） |
| 基本信息 | 姓名、城市、年龄段、学历 |
| 家庭结构 | 子女数量、子女教育阶段 |
| 资产与职业 | 资产级别（A8-A11）、职业类型、职位 |
| 核心诉求 | 资产配置/子女教育/风险规避/税务优化/养老规划/身份备份/商业拓展 |
| 意向国家 | 新加坡/土耳其/香港/美国/加拿大/英国/葡萄牙等 |
| 办理周期 | 6个月内/6-12个月/1-2年/不着急 |
| 补充信息 | 自由文本备注 |

## 🔐 数据安全

- 所有客户数据存储在本地 `data/crm.db` 文件中
- 建议定期备份数据库文件
- AI 分析时仅传输必要的业务数据，不包含敏感个人信息

## 📄 License

MIT License

---

**侨慧·本地CRM** - 让客户管理更安全、更智能
