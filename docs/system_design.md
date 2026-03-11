# System Design Document

## 0. End-to-End Request Flow (Current)

This is the runtime flow implemented by the current codebase (OpenAI/Anthropic/Gemini providers; no mock provider):

1. **HTTP request** → `POST /api/v1/execute`
2. **Middleware**
   - **LoggingMiddleware**: attaches `request_id` and `trace_id`, logs request start/end + latency
   - **AuthMiddleware**: validates JWT bearer token (skips `/api/v1/health`, `/docs`, `/openapi.json`, `/redoc`).  On failure returns a generic `"Authentication failed"` message — detailed reasons are logged internally only.
   - **RateLimitMiddleware**: Redis-backed per-user limit; returns 429 on limit exceeded
3. **Route handler** (`app/api/routes/execute.py`)
   - Reads the **authenticated identity from `request.state.user_id`** (JWT `sub` claim) — this is always the source of truth.
   - If `body.user_id` is provided and does **not** match the JWT subject, returns **403 Forbidden** immediately.
   - Delegates to the use case with the JWT identity.
4. **Use case** (`ExecuteTaskUseCase`)
   - validates/sanitizes `user_id` and `task`
   - creates/uses `session_id`
   - creates a `trace_id`
   - calls `MemoryService.verify_or_bind_session_owner(session_id, user_id)`:
     - **First use**: atomically claims the session owner in Redis (`SET NX`).
     - **Subsequent use**: reads the stored owner and returns **403** if it does not match the caller.
5. **Orchestrator** (`Orchestrator.execute`)
   - loads session memory from Redis
   - appends the user message to Redis
   - builds LLM messages (system prompt + history + current user task)
   - selects a provider via `ModelRouter` + `create_llm_provider`
   - calls the provider with tool schemas
   - if tool calls are returned:
     - executes tools via `ToolService` (timeout enforced)
     - logs each tool call with `trace_id`, `tool_name`, `duration_ms`, `status`
     - appends tool results to Redis
     - calls the provider again to produce the final assistant response
   - appends the final assistant response to Redis and trims messages if needed
6. **Response** returns a structured JSON payload including `tool_calls`, `memory` usage, `model_usage`, and `trace_id`

---

## 0.1 Security Model

### Identity & Authorization

| Layer | Mechanism | Behaviour |
|---|---|---|
| Authentication | JWT Bearer token (HS256) | AuthMiddleware validates on every protected route |
| Identity source of truth | `sub` claim in the JWT | Route handler reads `request.state.user_id` set by middleware |
| Body `user_id` | Optional, backward compat | Must match JWT sub if provided; mismatch → **403** |
| Session ownership | Redis key `session:{id}:owner` | Bound atomically on first use (`SET NX`); verified on every subsequent access |
| Cross-user session access | Blocked at use-case layer | Owner mismatch → **403** before any memory read/write |

### JWT Secret Requirements

- The app refuses to start in any environment **outside** `development`, `dev`, `testing`, or `test` if `JWT_SECRET` is:
  - The default placeholder `change-me-in-production`
  - Any well-known weak value (`secret`, `password`, …)
  - Shorter than **32 bytes**
- Generate a production secret:
  ```
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

### Auth Error Hygiene

- All authentication failures return a generic **`"Authentication failed"`** message to the client.
- Detailed reasons (expired token, bad signature, missing claim, etc.) are logged internally at `WARNING` level with `trace_id` for correlation — they are **never** included in the HTTP response body.

---

## 1. Memory Storage & Retrieval Strategy

### Session Memory (Redis)
- Each session stores messages as a Redis list keyed by `session:{session_id}:messages`.
- Messages are JSON-serialized and appended via `RPUSH`.
- Retrieval uses `LRANGE 0 -1` to load full conversation history.
- All keys have a configurable TTL (default: 1 hour) to prevent unbounded growth.

### Context Window Management
- **Token estimation** — a fast heuristic (~4 chars per token) is used to estimate message token counts before sending to the LLM.
- **Message trimming** — when message count exceeds `MAX_MESSAGES_PER_SESSION` (50), the oldest messages are trimmed via `LTRIM`.
- **Summary compression** — a background Celery task can summarize older messages into a condensed summary, stored at `session:{session_id}:summary`. The summary is prepended to the message list to preserve long-term context without exceeding the context window.

### Summary Trigger
- When messages exceed `SUMMARY_TRIGGER_TOKENS` (6000 estimated tokens), the system can dispatch a summarization task.
- The summary replaces older messages, preserving the most recent 5 messages plus the summary.

## 2. Tool Calling Structure

### Tool Interface
Every tool implements `ToolInterface` (ABC):
- `name()` — unique identifier
- `description()` — human-readable description for the LLM
- `parameters_schema()` — JSON Schema for input validation
- `execute(arguments)` — async execution returning `ToolCallResult`

### Tool Registry
- Central registry mapping tool names to implementations.
- Produces **OpenAI-style tool schemas** (function calling format). Non-OpenAI providers convert these schemas to their native function/tool formats.
- Tools are registered at startup; new tools are added by implementing the interface and registering.

### Execution Flow
1. LLM returns `tool_calls` in its response.
2. Orchestrator iterates over tool calls (max 5 per turn).
3. Each tool is resolved from registry, executed with timeout, and its result is appended to the message history.
4. The LLM is called again with tool results to produce a final response.

### Safety
- **Math tool** uses AST-based parsing — no `eval()`. Only arithmetic operators are allowed. Exponents are capped at 1000.
- **Web search** uses deterministic mock data — no external HTTP calls in default mode.
- All tool executions have a configurable timeout (default: 15s).

## 3. Rate Limiting

### Implementation
- Redis-based sliding window per-user rate limiter.
- Key pattern: `rate_limit:{user_id}:{minute_window}` where `minute_window = int(time()) // 60`.
- Uses `INCR` + `EXPIRE 60` for atomic counter management.
- Default: 30 requests per minute per user.

### Response
- Returns HTTP 429 with structured `ErrorResponse`:
  ```json
  {
    "error_code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Maximum 30 requests per minute.",
    "trace_id": "trace_...",
    "timestamp": "2024-..."
  }
  ```

### Configuration
- `RATE_LIMIT_PER_MINUTE` environment variable controls the limit.
- Rate limit check failures (Redis unavailable) fail open to avoid blocking legitimate requests.

## 4. Logging & Monitoring

### Structured Logging
- **Library**: structlog with JSON output.
- **Context propagation**: `request_id` and `trace_id` are attached to every log entry via Python contextvars.
- **Events logged**:
  - `request_started` / `request_completed` — HTTP lifecycle with duration_ms
  - `tool_called` / `tool_succeeded` / `tool_failed` — tool execution with trace_id, tool_name, duration_ms, status
  - `llm_called` / `llm_responded` — LLM invocations with provider, model, token usage
  - `memory_loaded` / `memory_saved` — session memory operations
  - `auth_failed` / `rate_limited` — security events

### Monitoring Strategy (Production)
- **Metrics**: expose Prometheus-compatible metrics (request count, latency percentiles, tool execution times, LLM token usage).
- **Dashboards**: Grafana dashboards for API health, tool usage patterns, LLM cost tracking.
- **Alerting**: CloudWatch alarms on error rate spikes, latency degradation, Redis memory usage.
- **Tracing**: OpenTelemetry-compatible trace IDs for distributed tracing via AWS X-Ray or Jaeger.

## 5. Scaling Strategy

### Horizontal Scaling
- **API servers** — stateless FastAPI instances behind a load balancer. Scale based on CPU/request count.
- **Redis** — ElastiCache cluster with read replicas for session data. Cluster mode for sharding if needed.
- **Workers** — Celery workers scale independently based on queue depth.

### Bottleneck Mitigation
- LLM API calls are the primary bottleneck. Mitigated by:
  - Async execution (non-blocking I/O).
  - Provider fallback (if OpenAI is slow, route to Anthropic or Gemini).
  - Request queuing via Celery for burst traffic.
- Redis operations are sub-millisecond; unlikely to be a bottleneck.

### Cost Optimization
- Model routing can direct simple tasks to cheaper models (gpt-4o-mini) and complex tasks to larger models.
- Choose a cheaper model (e.g. gpt-4o-mini, gemini-1.5-flash) for simple tasks to reduce cost.
- Message summarization reduces token usage for long sessions.

## 6. Security & Authentication

### JWT Authentication
- Bearer token authentication on all execute endpoints.
- Tokens contain `sub` (user_id), `role`, `iat`, `exp` claims.
- Health and documentation endpoints are exempted from auth.
- Token validation uses HS256 with a configurable secret.

### RBAC
- Three roles: `user`, `admin`, `internal`.
- Role-based guards can restrict access to specific operations.
- All users with valid tokens can execute tasks; admin endpoints can be gated.

### Secret Management
- No hardcoded secrets — all sensitive values loaded from environment variables via `pydantic-settings`.
- `.env.example` documents required variables without exposing values.
- In production: AWS Secrets Manager or Parameter Store.

## 7. Redis Usage Strategy

| Use Case | Key Pattern | Data Type | TTL |
|----------|-------------|-----------|-----|
| Session messages | `session:{id}:messages` | List (JSON strings) | 1 hour |
| Session summary | `session:{id}:summary` | String | 1 hour |
| Tool call history | `session:{id}:tool_history` | List (JSON strings) | 1 hour |
| Rate limiting | `rate_limit:{user}:{window}` | Counter (INCR) | 60 seconds |
| Celery broker | Internal Celery keys | Various | Managed by Celery |

### Why Redis
- Sub-millisecond latency for session lookups.
- Native TTL support for automatic cleanup.
- Atomic operations (INCR, RPUSH, LTRIM) for race-free rate limiting and message management.
- Celery broker support eliminates the need for a separate message queue.

## 8. Provider Selection (Current)

### Supported providers
- **OpenAI** (`openai`)
- **Anthropic** (`anthropic`)
- **Gemini** (`gemini`)

### Behavior
- The configured `DEFAULT_LLM_PROVIDER` is used unless explicitly overridden.
- **The chosen provider must have its API key configured** (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`), otherwise the request fails with a structured `LLM_PROVIDER_ERROR` response (HTTP 502).
