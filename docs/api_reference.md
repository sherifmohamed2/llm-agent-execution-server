# API Reference

**OpenAPI version:** 3.1.0  
**Service:** `agent-execution-engine` v1.0.0  
**Base URL:** `http://localhost:8000` (local) / your deployed host  
**Interactive docs:** [`/docs`](http://localhost:8000/docs) (Swagger UI) · [`/redoc`](http://localhost:8000/redoc) (ReDoc)

---

## Authentication

All endpoints **except `/api/v1/health`** require a JWT Bearer token.

```
Authorization: Bearer <token>
```

| Scheme | Type | Format |
|--------|------|--------|
| `BearerAuth` | HTTP Bearer | JWT (HS256) |

Generate a token locally:
```bash
python -c "from app.infrastructure.security.jwt import create_token; print(create_token(user_id='alice', role='user'))"
```

---

## Endpoints

### `GET /api/v1/health`

Check service liveness and dependency readiness. **No authentication required.**

| Property | Value |
|----------|-------|
| **Tag** | `health` |
| **Operation ID** | `health_check_api_v1_health_get` |
| **Auth required** | No |

#### Responses

##### `200 OK`

```json
{
  "status": "healthy",
  "app_name": "agent-execution-engine",
  "version": "1.0.0",
  "environment": "development",
  "checks": {
    "redis": "connected",
    "llm_provider": "openai"
  },
  "timestamp": "2026-03-11T10:00:00+00:00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | `"healthy"` when all checks pass; `"degraded"` when Redis is unavailable. |
| `app_name` | `string` | Application name from config. |
| `version` | `string` | Application version. |
| `environment` | `string` | Active environment (`development`, `production`, …). |
| `checks.redis` | `string` | `"connected"` or `"unavailable"`. |
| `checks.llm_provider` | `string` | Currently configured default LLM provider. |
| `timestamp` | `string` | ISO 8601 UTC timestamp. |

---

### `POST /api/v1/execute`

Execute a task using the AI agent. The agent will decide autonomously whether to call tools, and will return the final answer along with full execution metadata.

| Property | Value |
|----------|-------|
| **Tag** | `execute` |
| **Operation ID** | `execute_task_api_v1_execute_post` |
| **Auth required** | Yes — `Authorization: Bearer <token>` |
| **Content-Type** | `application/json` |

#### Request Body — `ExecuteRequest`

> **Required.** Extra fields are forbidden (`additionalProperties: false`).

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `task` | `string` | ✅ Yes | `minLength: 1`, `maxLength: 4096` | The instruction or question sent to the agent. |
| `user_id` | `string \| null` | No | `minLength: 1`, `maxLength: 128`, pattern `^[a-zA-Z0-9_\-]+$` | Optional, backward-compat. **Must exactly match the JWT `sub` claim** if provided — mismatch returns `403`. Omit to use the token identity automatically. |
| `session_id` | `string \| null` | No | `maxLength: 64` | Existing session to continue. If omitted a new session is created. The session is bound to the caller on first use (cross-user access returns `403`). |
| `metadata` | `object \| null` | No | — | Arbitrary key-value data. Stored but not used in execution. |

**Minimal request:**
```json
{
  "task": "What is 12 factorial?"
}
```

**Full request:**
```json
{
  "task": "What is 12 factorial?",
  "user_id": "alice",
  "session_id": "sess_abc123",
  "metadata": { "source": "mobile-app", "locale": "en-US" }
}
```

#### Response Body — `ExecuteResponse`

##### `200 OK`

```json
{
  "status": "completed",
  "session_id": "sess_abc123def456",
  "response": "12! = 479,001,600",
  "tool_calls": [
    {
      "tool_name": "math",
      "call_id": "call_xyz789",
      "status": "success",
      "result": { "expression": "factorial(12)", "value": 479001600 },
      "error": null,
      "duration_ms": 0.21
    }
  ],
  "memory": {
    "session_id": "sess_abc123def456",
    "message_count": 4,
    "has_summary": false
  },
  "model_usage": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "prompt_tokens": 72,
    "completion_tokens": 38,
    "total_tokens": 110
  },
  "trace_id": "trace_9f3a1b2c4d",
  "timestamp": "2026-03-11T10:00:00+00:00"
}
```

**Top-level fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `string` | ✅ | Execution status. Always `"completed"` on a `200` response. |
| `session_id` | `string` | ✅ | Session identifier. Pass this back as `session_id` in future requests to continue the conversation. |
| `response` | `string` | ✅ | The agent's final natural-language answer. |
| `tool_calls` | `ToolCallResponse[]` | ✅ | List of tools invoked during this turn (may be empty). |
| `memory` | `MemoryUsageResponse` | ✅ | Session memory state after this turn. |
| `model_usage` | `ModelUsageResponse` | ✅ | Token usage and provider metadata. |
| `trace_id` | `string` | ✅ | Unique request trace ID. Include in bug reports. |
| `timestamp` | `string` | ✅ | ISO 8601 UTC timestamp of the response. |

##### `422 Unprocessable Entity`

Returned when the request body fails schema validation (missing required field, unknown extra field, value out of range, etc.).

```json
{
  "detail": [
    {
      "loc": ["body", "task"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

See [`HTTPValidationError`](#httpvalidationerror) schema below.

#### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Task completed successfully. |
| `400` | Bad Request — malformed `user_id` or task content. |
| `401` | Unauthorized — missing, expired, or invalid Bearer token. |
| `403` | Forbidden — `user_id` in body does not match JWT `sub`, or session is owned by a different user. |
| `422` | Unprocessable Entity — request body validation failed. |
| `429` | Too Many Requests — per-user rate limit exceeded (default: 30 req/min). |
| `502` | Bad Gateway — upstream LLM provider returned an error. |
| `503` | Service Unavailable — Redis is unreachable. |

---

## curl Examples

### Health check
```bash
curl http://localhost:8000/api/v1/health
```

### Execute — math task (no session)
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"task": "Calculate 25 * 4"}'
```

### Execute — continue an existing session
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Now double that result",
    "session_id": "sess_abc123def456"
  }'
```

### Execute — with backward-compat user_id (must match JWT sub)
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Search for Python tutorials",
    "user_id": "alice"
  }'
```
