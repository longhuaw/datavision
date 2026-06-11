# DataVision - 智能数据可视化低代码平台

<div align="center">

  ⚡ **输入一句话，自动生成专业图表和数据大屏**

  [![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
  [![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
  [![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql)](https://mysql.com)
  [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

## ✨ 核心功能

- 🔥 **NL2SQL 自然语言生成图表** — "近30天各品类销售额趋势" → 自动 SQL + 图表
- 📊 **20+ 图表类型** — 折线图、柱状图、饼图、热力图、地图、雷达图等
- 🎨 **拖拽看板设计器** — 自由布局，图表联动，多主题模板
- 🤖 **AI 智能助手** — 图表推荐、异常检测、自动洞察
- 🔗 **多数据源接入** — MySQL、PostgreSQL、ClickHouse、API、Excel
- 📤 **一键发布分享** — 链接/嵌入/密码保护/定时推送

## 🚀 快速开始

### 前置要求
- Docker & Docker Compose
- 或 Python 3.12+ / Node.js 22+ / MySQL 8.0+ / Redis 7+

### Docker 一键部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/yourname/datavision.git
cd datavision

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 中必要的配置（数据库密码、JWT密钥等）

# 3. 启动所有服务
docker compose up -d

# 4. 访问
# 前端: http://localhost:3000
# API文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health
```

### 本地开发

#### 后端

```bash
cd backend
pip install -r requirements.txt
# 配置 .env
alembic upgrade head        # 数据库迁移
uvicorn app.main:app --reload --port 8000
```

#### 前端

```bash
cd frontend
npm install
npm run dev                # http://localhost:5173
```

## 📁 项目结构

```
datavision/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/        # API 路由
│   │   ├── models/        # SQLAlchemy 模型
│   │   ├── schemas/       # Pydantic 校验
│   │   ├── services/      # 业务逻辑
│   │   ├── core/          # 核心工具(NL2SQL/SQL执行器/缓存)
│   │   └── middleware/    # 中间件(JWT/日志/限流)
│   └── alembic/           # 数据库迁移
├── frontend/              # React 前端
│   └── src/
│       ├── pages/         # 页面组件
│       ├── components/    # 通用组件
│       └── store/         # 状态管理
├── deploy/                # 部署配置
└── docker-compose.yml     # 服务编排
```

## 🛠 技术栈

| 层次 | 技术 |
|------|------|
| 后端框架 | FastAPI 0.115 (Python 3.12) |
| ORM | SQLAlchemy 2.0 (异步) |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7 |
| 任务队列 | Celery 5 |
| 前端框架 | React 18 + TypeScript |
| UI 库 | Ant Design 5 |
| 图表库 | ECharts 5 |
| AI | LangChain + OpenAI |
| 部署 | Docker Compose |

## 📖 API 文档

启动后端后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🗺 路线图

- [x] 基础平台（认证/数据源/数据集）
- [ ] 图表引擎（10+图表类型）
- [ ] NL2SQL 自然语言转 SQL 🔥
- [ ] 看板设计器（拖拽布局/联动）
- [ ] AI 增强（推荐/检测/洞察）
- [ ] 发布分享与模板市场

## 📝 License

MIT © 2024 DataVision
