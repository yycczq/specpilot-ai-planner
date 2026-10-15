# SpecPilot 项目说明与开发指南

SpecPilot 是一个 AI 辅助产品需求与方案策划工作台。它把自然语言想法整理成推荐方向、MVP 范围、分阶段计划、成功指标、待确认问题、验收标准、API 草案和测试用例。生成内容始终是草案，需要由产品和开发人员审阅。

## 功能概览

- React 工作台：填写想法、加载样例、查看与编辑生成结果、复制或导出 Markdown。
- Django REST API：生成和管理需求草案、记录修订历史、搜索和分页查询。
- 账号 API：注册、用户名/邮箱登录、Token 认证；登录后的需求及历史按账号隔离。
- AI 接入：本地 `mock` 模板、服务端 Anthropic API，或用户自带的 OpenAI 兼容 Chat Completions API。
- 持久化与缓存：MySQL 用于 Docker Compose；SQLite 适合轻量本地开发；Redis 可用于共享缓存和限流。

`mock` 模式不会调用模型。它提供固定结构的演示策划，不会真正理解每条输入。需要针对想法生成个性化建议时，请连接真实模型 API。

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 前端 | React 19、Vite、原生 CSS |
| 后端 | Python 3.12、Django 5.2、Django REST Framework |
| 数据库 | MySQL 8.4 或 SQLite |
| 缓存 | Redis，未配置时使用进程内缓存 |
| AI | Anthropic Messages API、OpenAI 兼容 Chat Completions、演示 mock |

## 项目结构

```text
.
├── backend/
│   ├── config/                 # Django 项目设置与 URL
│   ├── specs/                  # 需求、用户认证、AI 服务、API 和测试
│   ├── manage.py
│   └── dev_server.py           # PyCharm 本地 SQLite/mock 启动入口
├── frontend/
│   ├── src/                    # React 页面与样式
│   ├── package.json
│   └── vite.config.js          # /api 代理到 Django
├── docs/
│   ├── API.md                  # REST 接口、认证与请求示例
│   ├── AI_WORKFLOW.md          # AI 辅助开发记录
│   └── UI_REFERENCES.md       # 界面研究来源与实现说明
├── docker-compose.yml
└── .env.example
```

## 快速启动：Docker Compose

需要 Docker Desktop/Engine 和 Docker Compose。

```bash
cp .env.example .env
docker compose up --build
```

首次构建会安装依赖，后端容器会执行 Django 数据库迁移。

- 前端：<http://localhost:5173>
- 后端健康检查：<http://localhost:8000/api/health/>
- Django 管理后台：<http://localhost:8000/admin/>

停止服务：

```bash
docker compose down
```

如需连同 MySQL 数据卷一起删除，请先备份需要的数据，再运行 `docker compose down -v`。这会永久删除该 Compose 项目的本地数据库卷。

`.env.example` 的默认设置适合本机演示。公开部署前请参考“部署前配置”，不要直接使用示例密钥和默认数据库密码。

## 本地开发：PyCharm 或终端

### 后端

从项目根目录执行：

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
USE_SQLITE=true AI_PROVIDER=mock .venv/bin/python manage.py migrate
USE_SQLITE=true AI_PROVIDER=mock .venv/bin/python manage.py runserver 127.0.0.1:8000
```

也可以在 PyCharm 中选择项目虚拟环境 `backend/.venv`，使用运行配置 **SpecPilot Backend (mock)**。该配置通过 `backend/dev_server.py` 启动 Django，并使用 SQLite 与 mock 模式。

本地 SQLite 文件位于 `backend/db.sqlite3`，已加入 Git 忽略规则。重置本地演示数据时，先停止后端，再删除该文件并重新执行 `migrate`。

### 前端

打开另一个终端：

```bash
cd frontend
corepack enable
pnpm install
pnpm dev
```

Vite 在开发模式下将 `/api` 请求代理到 `http://localhost:8000`。Redis 未配置时，Django 自动使用本地进程缓存。

## AI 服务配置

### 本地模板演示

保持 `AI_PROVIDER=mock` 即可运行，不需要密钥。输出是模板示例，不应当当作对输入的真实 AI 分析。

### 使用自己的模型 API

在工作台打开“API 设置”，填写兼容 Chat Completions 的 Base URL、模型 ID 和 API Key，然后测试连接。Key 只在当前页面内存和本次请求中使用；SpecPilot 不把它保存到浏览器存储、数据库、缓存或需求档案。

安全限制：BYOK API 目标需要公开 HTTPS。仅当 `ALLOW_LOCAL_BYOK=true` 时，开发环境中的 `localhost` 可使用 HTTP。不要把自己的 API Key 提交到代码仓库或截图里。

### 服务端 Anthropic

在本机 `.env` 或部署平台的环境变量中设置：

```dotenv
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=替换为你自己的密钥
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

`.env` 已被 Git 忽略。只提交 `.env.example` 里的空白占位配置，不提交真实密钥。

## 数据与认证

- `Spec` 保存原始需求、生成结果 JSON、状态和创建/更新时间。
- `SpecRevision` 保存人工审阅前的结果快照。
- Django 用户和 Token 用于 API 账号认证；Token 默认 30 天过期。
- 登录账号只读取自己的需求。为兼容本地演示，匿名数据可以单独保存在共享演示空间；通过 `DEMO_ALLOW_ANONYMOUS=false` 关闭匿名读写。
- SQLite 数据文件、MySQL Docker 数据卷都只存在于运行环境，不应上传到 GitHub。

账号接口和数据管理示例见 [REST API 说明](API.md)。当前前端工作台尚未接入登录表单；账号注册和认证可通过 API 调用。

## 测试与构建

```bash
cd backend
USE_SQLITE=true AI_PROVIDER=mock .venv/bin/python manage.py check
USE_SQLITE=true AI_PROVIDER=mock .venv/bin/python manage.py makemigrations --check --dry-run
USE_SQLITE=true AI_PROVIDER=mock .venv/bin/python manage.py test
cd ../frontend
pnpm build
```

GitHub Actions 会在推送和 Pull Request 时运行后端检查、迁移检查、测试以及前端生产构建。

## 部署前配置

这是作品集原型。正式公开部署前至少需要：

1. 设置随机生成且保密的 `DJANGO_SECRET_KEY`，设 `DJANGO_DEBUG=false` 并配置精确的 `DJANGO_ALLOWED_HOSTS`。
2. 设置 `DEMO_ALLOW_ANONYMOUS=false`，通过 HTTPS 提供服务，并把数据库和 Redis 放在受控网络中。
3. 在前端接入账号注册/登录与 Token 生命周期管理；当前虽有认证 API，但界面还未接上。
4. 将 AI 密钥放入部署平台的密钥管理中，设置调用预算、监控、备份和数据保留策略。
5. 核对跨域来源、速率限制、数据库备份恢复及隐私说明，再开放给真实用户。

环境变量含义、API 请求限制和部署边界也见 [.env.example](../.env.example) 与 [API 文档](API.md)。
