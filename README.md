# Agent Execution Engine

A production-grade AI Agent Execution Server built with FastAPI, featuring multi-LLM provider support, tool calling, session memory, and structured observability.

## Table of Contents

- [Architecture](#architecture)
- [Folder Structure](#folder-structure)
- [Execution Flow](#execution-flow)
- [Memory Strategy](#memory-strategy)
- [Tools](#tools)
- [LLM Providers](#llm-providers)
- [Authentication & Rate Limiting](#authentication--rate-limiting)
- [Local Setup](#local-setup)
  - [Prerequisites](#prerequisites)
  - [Create a virtual environment](#1-create-a-virtual-environment)
  - [Install dependencies](#2-install-dependencies)
  - [Configure environment](#3-configure-environment)
  - [Run the server](#5-run-the-server)
  - [Generate a test token](#6-generate-a-test-token)
  - [Test the API with FastAPI docs](#8-test-the-api-with-fastapi-docs)
- [Docker Usage](#docker-usage)
- [API Examples](#api-examples)
- [AWS Deployment Note](#aws-deployment-note)
- **Docs**
  - **Full API reference (OpenAPI)**: [docs/api_reference.md](docs/api_reference.md)
  - **Architecture diagram + responsibilities**: [docs/architecture.md](docs/architecture.md#architecture-overview)
  - **System design + end-to-end flow**: [docs/system_design.md](docs/system_design.md#0-end-to-end-request-flow-current)
  - **Advanced agent answers (Stage 3)**: [docs/advanced_agent_answers.md](docs/advanced_agent_answers.md)
  - **High-Level System Diagram (step1)**: [docs/High-Level System Diagram.excalidraw](docs/High-Level%20System%20Diagram.excalidraw)

## Architecture

The system follows a **simplified layered architecture** designed for clarity and maintainability:

```
┌─────────────────────────────────────────────────┐
│  API Layer (routes, schemas, middleware)         │
├─────────────────────────────────────────────────┤
│  Application Layer (use cases, services, DTOs)  │
├─────────────────────────────────────────────────┤
│  Domain Layer (models, interfaces, enums)        │
├─────────────────────────────────────────────────┤
│  Infrastructure Layer (providers, Redis, tools)  │
├─────────────────────────────────────────────────┤
│  Workers (Celery background tasks)               │
└─────────────────────────────────────────────────┘
```

- **API** — thin routes, Pydantic schemas, cross-cutting middleware (auth, logging, rate limiting).
- **Application** — business orchestration, memory management, tool execution, model routing.
- **Domain** — pure Python models and interfaces with zero framework dependencies.
- **Infrastructure** — concrete implementations: LLM providers, Redis store, tool implementations.
- **Workers** — Celery tasks for background processing (memory summarization).

## Folder Structure

```
app/
├── main.py                          # FastAPI application factory
├── api/
│   ├── routes/
│   │   ├── execute.py               # POST /api/v1/execute
│   │   └── health.py                # GET /api/v1/health
│   ├── schemas/
│   │   ├── execute.py               # Request/response models
│   │   └── error.py                 # Error response model
│   └── middleware/
│       ├── logging.py               # Request/response logging
│       ├── auth.py                  # JWT authentication
│       └── rate_limit.py            # Per-user rate limiting
├── application/
│   ├── use_cases/
│   │   └── execute_task.py          # Main execution use case
│   ├── services/
│   │   ├── orchestrator.py          # Core execution loop
│   │   ├── memory_service.py        # Session memory management
│   │   ├── tool_service.py          # Tool resolution & execution
│   │   ├── model_router.py          # LLM provider selection
│   │   └── audit_service.py         # Execution audit logging
│   └── dto/
│       └── execution_result.py      # Internal result model
├── domain/
│   ├── models/                      # Pure data classes
│   ├── interfaces/                  # ABC contracts
│   └── enums/                       # Status, error, role enums
├── infrastructure/
│   ├── llm/                         # OpenAI, Anthropic, Gemini providers
│   ├── memory/                      # Redis session store
│   ├── tools/                       # Math, Web Search, Registry
│   ├── security/                    # JWT, RBAC
│   └── logging/                     # Structured logging setup
├── core/
│   ├── config.py                    # pydantic-settings configuration
│   ├── constants.py                 # Application constants
│   ├── exceptions.py                # Typed custom exceptions
│   └── utils.py                     # Utility functions
└── workers/
    ├── celery_app.py                # Celery configuration
    └── tasks.py                     # Background tasks
```

## Execution Flow

```
POST /api/v1/execute
    │
    ├── Middleware: LoggingMiddleware (attach request_id, trace_id)
    ├── Middleware: AuthMiddleware (validate JWT, extract user)
    ├── Middleware: RateLimitMiddleware (check per-user limit)
    │
    ▼
ExecuteTaskUseCase
    ├── Validate & sanitize inputs
    ├── Generate session_id (if not provided) and trace_id
    │
    ▼
Orchestrator.execute()
    ├── 1. Load session memory from Redis
    ├── 2. Append user message to memory
    ├── 3. Assemble messages (system prompt + history + user task)
    ├── 4. Call LLM provider with tool schemas
    ├── 5. If LLM returns tool_calls:
    │       ├── Execute each tool via ToolService
    │       ├── Log tool call (trace_id, tool_name, duration_ms, status)
    │       ├── Append tool results to memory
    │       └── Call LLM again with tool results
    ├── 6. Save assistant response to memory
    ├── 7. Trim messages if over limit
    └── 8. Return ExecutionResult
```

## Memory Strategy

| Layer | Storage | TTL | Purpose |
|-------|---------|-----|---------|
| Working Memory | In-process (message list) | Per-request | Current context window |
| Session Memory | Redis List | 1 hour | Conversation history |
| Session Summary | Redis String | 1 hour | Compressed older context |
| Tool History | Redis List | 1 hour | Audit trail of tool calls |

Messages are trimmed when count exceeds 50. A Celery background task can compress older messages into a summary for long-running sessions.

## Tools

| Tool | Type | Description |
|------|------|-------------|
| `math` | Safe arithmetic | AST-based expression evaluation. No `eval()`. Supports `+`, `-`, `*`, `/`, `//`, `%`, `**`. Exponents capped at 1000. |
| `web_search` | Mock search | Deterministic mock results by keyword matching. Returns structured search results. |

Tools implement `ToolInterface` (ABC) and are registered in `ToolRegistry`. Adding a new tool requires implementing the interface and registering it — no changes to the orchestrator.

## LLM Providers

| Provider | Status | Notes |
|----------|--------|-------|
| OpenAI | Default | Uses `gpt-4o-mini` by default. Set `OPENAI_API_KEY`. |
| Anthropic | Optional | Uses `claude-3-5-sonnet`. Set `ANTHROPIC_API_KEY`. |
| Gemini | Optional | Uses `gemini-1.5-flash`. Set `GEMINI_API_KEY`. |

Default provider is OpenAI. Set `DEFAULT_LLM_PROVIDER` to `openai`, `anthropic`, or `gemini`. The chosen provider must have its API key set. All providers implement `LLMProviderInterface` and return normalized `LLMResponse` objects.

## Authentication & Rate Limiting

**Authentication:**
- JWT Bearer tokens on all `/execute` endpoints.
- Health and docs endpoints are exempted.
- Tokens carry `sub` (user_id), `role`, `iat`, `exp` claims.

**Rate Limiting:**
- Redis-backed per-user sliding window.
- Default: 30 requests per minute.
- Returns HTTP 429 with structured error response.

## Local Setup

### Prerequisites
- Python 3.9+ (3.12 recommended)
- Redis (or Docker for Redis)

### 1. Create a virtual environment

From the project root:

```bash
# Create the venv (e.g. in a folder named .venv)
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate
# On Windows (cmd):
#   .venv\Scripts\activate.bat
# On Windows (PowerShell):
#   .venv\Scripts\Activate.ps1
```

You should see `(.venv)` in your shell prompt when it’s active.

### 2. Install dependencies

With the venv activated:

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY (default provider) and optionally ANTHROPIC_API_KEY, GEMINI_API_KEY
```

### 4. (Optional) Start Redis

If you’re not using Docker, ensure Redis is running locally (e.g. `redis-server`). The app needs Redis for session memory and rate limiting.

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be at `http://localhost:8000`. Docs: `http://localhost:8000/docs`.

### 6. Generate a test token

In another terminal (with the same venv activated):

```bash
python -c "from app.infrastructure.security.jwt import create_token; print(create_token(user_id='test_user', role='user'))"
```

Use this token in the `Authorization: Bearer <token>` header when calling `/api/v1/execute`.

### 7. Run tests

```bash
python -m pytest
```

### 8. Test the API with FastAPI docs

With the server running, you can call the API from your browser using the built-in docs:

1. **Swagger UI (interactive)**  
   Open: [http://localhost:8000/docs](http://localhost:8000/docs)

2. **Authorize**  
   - Click **Authorize** (top right).  
   - In **Value**, enter: `Bearer <your_token>` (replace `<your_token>` with the token from step 6).  
   - Click **Authorize**, then **Close**.

3. **Try the execute endpoint**  
   - Expand **POST /api/v1/execute**.  
   - Click **Try it out**.  
   - Use a request body like:
     ```json
     {"user_id": "test_user", "task": "Calculate 25 * 4"}
     ```
   - Click **Execute**. You should get a 200 response with the result and any tool calls.

4. **ReDoc (read-only)**  
   Open: [http://localhost:8000/redoc](http://localhost:8000/redoc) for a clean, read-only API reference.

## Docker Usage

### Build and Run
```bash
docker-compose up --build
```

This starts:
- **app** — FastAPI server on port 8000
- **redis** — Redis on port 6379
- **worker** — Celery worker for background tasks

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

## API Examples

### Execute a Math Task
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"user_id": "user_123", "task": "Calculate 25 * 4"}'
```

### Execute a Search Task
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"user_id": "user_123", "task": "Search for Python tutorials"}'
```

### Continue a Session
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"user_id": "user_123", "task": "What else can you tell me?", "session_id": "sess_abc123"}'
```

### Example Response
```json
{
  "status": "completed",
  "session_id": "sess_abc123def456",
  "response": "The result of the calculation is: 100.0",
  "tool_calls": [
    {
      "tool_name": "math",
      "call_id": "call_math_001",
      "status": "success",
      "result": {"expression": "25 * 4", "value": 100.0},
      "error": null,
      "duration_ms": 0.15
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
    "prompt_tokens": 70,
    "completion_tokens": 40,
    "total_tokens": 110
  },
  "trace_id": "trace_abc123",
  "timestamp": "2024-01-01T00:00:00+00:00"
}
```

## AWS Deployment Note

For production deployment on AWS:
- Deploy the FastAPI app on **ECS Fargate** or **EKS** behind an **ALB**.
- Use **ElastiCache (Redis)** for session storage and rate limiting.
- Store secrets in **AWS Secrets Manager**.
- Enable **CloudWatch** for logs and metrics, **X-Ray** for distributed tracing.
- Use **ECR** for container image storage.
- Configure auto-scaling based on CPU utilization and request count.

See `docs/architecture.md` for the full deployment architecture diagram.
