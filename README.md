# SpecPilot

**把模糊想法，变成可讨论、可验证的需求。**

SpecPilot 是一个 AI 辅助需求工作台原型。输入一段自然语言想法后，它会给出推荐方向、MVP 边界、分阶段执行计划和可验证指标，并补充待确认问题、验收标准、API 草案和测试用例；开发者可以编辑草案、确认版本并导出 Markdown。模型输出始终是待审阅内容，不会被自动当作正确规格。

## 为什么做这个项目

本项目面向 AI 原生开发流程：在需求不完整时快速形成可讨论原型，再由开发者检查、测试和迭代。它同时展示 Python Web API、数据库持久化、Redis 缓存、AI 服务接入、前端交互和自动化测试。

## 功能

- 自然语言需求输入、可修改的场景模板和无密钥演示样例。
- AI 生成推荐方案及理由、首版做/不做范围、分阶段任务与交付物、指标口径、假设、澄清问题、用户故事、验收标准、接口草案、测试用例与风险提示。
- 支持无密钥本地演示、服务端 Anthropic 配置，以及用户自带 OpenAI 兼容 API（自定义 Base URL、模型和 API Key）。
- API Key 只随当前请求发送，不保存到数据库、缓存或浏览器存储；自带 API 的生成结果不进入共享缓存。
- 人工编辑全部草案字段、标记已确认、载入历史版本，并保留修改前快照。
- 搜索需求档案，复制或导出 Markdown。
- 支持账号注册、用户名/邮箱登录和 Token API 认证；登录后的需求数据按账号隔离。
- 提供 API 连接测试、REST 接口调用示例和健康状态提示。
- React 单页工作台、Django REST API、MySQL 持久化和 Redis 缓存。
- Docker Compose 本地启动，GitHub Actions 运行后端测试和前端构建。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19、Vite、原生 CSS |
| API | Python 3.12、Django 5、Django REST Framework |
| 数据库 | MySQL 8.4；测试和轻量开发可用 SQLite |
| 缓存 | Redis |
| AI | OpenAI 兼容 Chat Completions（用户自带 API）、Anthropic Messages API、mock 演示模式 |
| 验证 | Django TestCase、GitHub Actions |

## 本地运行

需要 Docker Desktop 或 Docker Engine 和 Docker Compose。

```bash
cp .env.example .env
docker compose up --build
```

打开 `http://localhost:5173`。默认使用 mock 模式，不需要 API Key。后端健康检查地址为 `http://localhost:8000/api/health/`。

启用服务端 Anthropic 模式时，在 `.env` 中设置 `AI_PROVIDER=anthropic` 和 `ANTHROPIC_API_KEY`，再重启服务。也可以在工作台右上角选择“配置 API”，填写自己的 OpenAI 兼容 Base URL、模型和 Key；界面不会将 Key 写入浏览器存储，后端也不会持久化它。

## 测试

```bash
cd backend
USE_SQLITE=true AI_PROVIDER=mock python manage.py test
```

```bash
cd frontend
pnpm install
pnpm build
```

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health/` | 服务状态和当前 AI provider 名称 |
| `POST` | `/api/auth/register/` | 创建账号并返回 API Token |
| `POST` | `/api/auth/login/` | 用户名或邮箱登录 |
| `POST` | `/api/auth/logout/` | 撤销当前 Token |
| `GET` | `/api/auth/me/` | 查询当前登录账号 |
| `GET` | `/api/overview/` | 草案数量统计 |
| `GET` | `/api/specs/` | 需求档案，可用 `?q=` 搜索及 `limit`、`offset` 分页 |
| `POST` | `/api/specs/` | 分析并保存一条需求 |
| `GET` | `/api/specs/{id}/` | 查看需求详情 |
| `PATCH` | `/api/specs/{id}/` | 保存人工审阅结果和修改前快照 |
| `GET` | `/api/specs/{id}/revisions/` | 查看修改历史 |
| `POST` | `/api/providers/test/` | 测试用户自带的 OpenAI 兼容 API |

调用字段、curl 示例、BYOK 限制和部署边界见 [REST API 文档](docs/API.md)。

## UI 参考与 AI 开发记录

- [项目说明与开发指南](docs/PROJECT_GUIDE.md)
- [REST API 文档](docs/API.md)
- [界面参考来源及实现说明](docs/UI_REFERENCES.md)
- [AI 辅助开发记录](docs/AI_WORKFLOW.md)

## 当前边界

- 这是用于作品集展示的原型。API 已提供 Token 注册登录、30 天 Token 期限和账号级需求隔离；前端登录界面尚未接入。匿名演示模式的数据仍是共享的，公开部署前应设置 `DEMO_ALLOW_ANONYMOUS=false`，并完成前端登录、HTTPS、密钥和监控等生产配置。
- mock 模式提供结构化策划模板，不调用真实模型，也不代表个性化分析或生成质量评估；接入自有 API 后才会基于输入生成内容。
- Anthropic 模式需在服务端配置 API Key；BYOK 支持 OpenAI 兼容 Chat Completions。模型输出需要开发者复核。
- 当前版本不生成或执行任意代码，只提供可审阅的规格与测试草案。
- BYOK Base URL 限定为公开 HTTPS 地址（localhost 开发环境可用 HTTP），降低 SSRF 风险。
