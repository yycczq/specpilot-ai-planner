# SpecPilot REST API

The API is served by Django REST Framework. With the local Docker Compose setup, use `http://localhost:8000` as the base URL. Requests and responses use JSON.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health/` | Service and database readiness; returns `503` if the database is unavailable. |
| `POST` | `/api/auth/register/` | Create an account and return an API token. |
| `POST` | `/api/auth/login/` | Sign in by username or email and return an API token. |
| `POST` | `/api/auth/logout/` | Revoke the current token. Requires authentication. |
| `GET` | `/api/auth/me/` | Return the authenticated account. Requires authentication. |
| `GET` | `/api/overview/` | Total, draft, and reviewed counts. |
| `GET` | `/api/specs/?q=keyword&limit=50&offset=0` | Search and page through Specs; `q` is limited to 100 characters and `limit` to 1–50. Returns `X-Total-Count` and, when more results exist, `X-Next-Offset` headers. |
| `POST` | `/api/specs/` | Analyze a requirement and save its draft. |
| `GET` | `/api/specs/{id}/` | Read a spec. |
| `PATCH` | `/api/specs/{id}/` | Save a reviewed result and record the previous result as a revision. |
| `GET` | `/api/specs/{id}/revisions/` | List saved prior versions. |
| `POST` | `/api/providers/test/` | Send a small request to check an OpenAI-compatible API configuration. |

## Accounts and private data

Register with a username, email, and password. Passwords are validated and stored using Django's password hashing; the API never returns them.

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"choose-a-strong-password"}'
```

The response includes `token` and a public `user` object. Use the token on subsequent requests:

```bash
curl http://localhost:8000/api/auth/me/ \
  -H 'Authorization: Token YOUR_TOKEN'
```

Login accepts either a username or email at `/api/auth/login/`:

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice@example.com","password":"your-password"}'
```

Tokens expire after 30 days. Login replaces an expired token, and `POST /api/auth/logout/` with the `Authorization` header revokes the active token. Each account currently has one active token, so logging out revokes it for all clients. Authenticated list, detail, revision, and overview endpoints only include the current user's Specs. Attempts to access another account's Spec return `404`.

Temporary default-provider response caching is scoped to the account, so matching requirements from different accounts do not share cached results. Anonymous demo requests share one demo cache scope, consistent with their shared workspace.

For backwards-compatible local demos, unauthenticated requests can still use an anonymous workspace when `DEMO_ALLOW_ANONYMOUS=true`; anonymous Specs are shared with other anonymous requests and remain separate from signed-in accounts. Set `DEMO_ALLOW_ANONYMOUS=false` for a deployment that requires login. Health checks and account registration/login remain public.

## Generate with your own API

`provider` is optional. If omitted, SpecPilot uses the server's `AI_PROVIDER` setting. When provided, it must contain an OpenAI-compatible Chat Completions endpoint, model ID, and API key:

```bash
curl -X POST http://localhost:8000/api/specs/ \
  -H 'Content-Type: application/json' \
  -d '{
    "requirement": "玩家可以提交游戏内问题并查询处理进度",
    "provider": {
      "base_url": "https://api.openai.com/v1",
      "model": "your-model-id",
      "api_key": "your-api-key"
    }
  }'
```

The API key is accepted for the current request only. It is not written to the database, cache, or response. BYOK results are not cached so different accounts cannot share cached output. The requirement and generated result are saved as a Spec, as they are for normal `POST /api/specs/` requests.

`result` includes a `recommendation` string, `mvp_scope` object (`in_scope` and `out_of_scope` string arrays), `implementation_plan` array (phase, objective, task list, and deliverable), `success_metrics` array (name, definition, and target), and `assumptions` string array. It also includes `summary`, `questions`, `user_stories`, `acceptance_criteria`, `api_endpoints`, `test_cases`, and `risks`. For example:

```json
{
  "recommendation": "先验证一条核心用户流程，再根据使用证据扩展。",
  "mvp_scope": {
    "in_scope": ["完成主流程"],
    "out_of_scope": ["暂不做复杂报表"]
  },
  "implementation_plan": [
    {
      "phase": "阶段一：验证",
      "objective": "确认目标用户能完成核心任务。",
      "tasks": ["明确流程", "记录试用问题"],
      "deliverable": "试用记录和问题清单"
    }
  ],
  "success_metrics": [
    {
      "name": "核心任务完成率",
      "definition": "完成任务人数 ÷ 开始任务人数",
      "target": "先建立基线，再由团队设定目标"
    }
  ],
  "assumptions": ["首版聚焦一个主要用户场景"]
}
```

The `mock` provider returns a clearly labeled template and does not personalize the plan with a model. Configure a real provider for idea-specific recommendations.

To test a provider before generating a spec:

```bash
curl -X POST http://localhost:8000/api/providers/test/ \
  -H 'Content-Type: application/json' \
  -d '{
    "provider": {
      "base_url": "https://api.openai.com/v1",
      "model": "your-model-id",
      "api_key": "your-api-key"
    }
  }'
```

The test response is `{"status":"ok","provider":"openai-compatible"}`. Provider error bodies and credentials are not returned to callers.

## Review and revisions

```bash
curl -X PATCH http://localhost:8000/api/specs/SPEC_ID/ \
  -H 'Content-Type: application/json' \
  -d '{"result":{"title":"Reviewed title","summary":"Reviewed summary"},"status":"reviewed"}'
```

In a full client, send the complete result object returned from `GET /api/specs/{id}/`; the shortened object above is only a shape example. Each successful patch stores the previous result in the revisions endpoint.

## Limits and deployment

- Requirement input is limited to 5,000 characters; request bodies are limited to 3 MB; generated and edited JSON results are limited to 2 MB. Search terms are limited to 100 characters. Spec lists support `limit` (1–50) and `offset` (0–1,000,000), with total and next-offset headers exposed to browser clients.
- Authentication, generation, provider checks, and edits are rate limited per account or client IP: registration 5/hour, login 10/minute, provider checks 10/minute, generation 30/hour, and edits 120/hour. Configure Redis for shared throttling across multiple workers.
- BYOK supports OpenAI-compatible `POST /chat/completions`; provider-specific request formats such as Anthropic Messages are not accepted by this endpoint.
- BYOK targets must use public HTTPS. HTTP is allowed only for `localhost` development when `ALLOW_LOCAL_BYOK=true` (defaults to `DJANGO_DEBUG`). DNS answers are checked and pinned to public IPs to prevent requests to private network services.
- Token authentication and per-user Spec isolation are implemented. Tokens expire after 30 days and can be revoked on logout. Production must set a private `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, explicit `DJANGO_ALLOWED_HOSTS`, and `DEMO_ALLOW_ANONYMOUS=false`; startup rejects the built-in and `.env.example` placeholder secrets. Use HTTPS and configure backups, monitoring, and per-user token management before production use.
- A BYOK API key crosses the browser-to-SpecPilot connection and is then sent to the configured provider. Use HTTPS for deployed SpecPilot and provide only keys you control.
