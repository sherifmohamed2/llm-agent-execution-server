# Advanced Agent Thinking — Depth Test Answers

## 1. How would you design a multi-agent delegation system?

Use a **supervisor → worker** pattern.

- **Supervisor**: plans, delegates, enforces budgets (time/tokens), aggregates results.
- **Workers**: specialized prompts + tool access (e.g., “research”, “code”, “data”), same interface.
- **Transport**: queue-based (Redis Streams/SQS) with `correlation_id`, `parent_id`, `depth`, `attempt`.

Execution:
- Build a small task DAG, run independent tasks in parallel, aggregate, then finalize.
Guards:
- Max depth, per-worker timeouts, circuit breakers, and per-request token budgets.

## 2. How would you prevent tool hallucination?

Tool hallucination occurs when the LLM invokes a tool that doesn't exist or passes invalid arguments.

Prevention:
- **Only show registered tools**: tool registry is the source of truth.
- **Validate name + args**: reject unknown tools; JSON-schema validate args; range checks.
- **Constrain when possible**: provider “tool_choice=auto/none” or equivalents.
- **Repair loop with limit**: if validation fails, re-prompt with a short correction instruction (max N retries).
- **Observability**: log every attempted tool call (name, args, status) and alert on spikes.

## 3. How would you manage long-term memory beyond context window?

Use a tiered approach:
- **L1 Working**: current prompt window (system + recent turns + tool outputs).
- **L2 Session**: Redis message history + rolling summary (compress older turns).
- **L3 Long-term**: vector store for durable facts/preferences with metadata + TTL/versioning.

Retrieval:
- Fetch top‑k L3 memories relevant to the current query, then add L2 summary + most recent L1.
Write-back:
- After each turn, extract “facts worth remembering” into L3 (explicit schema, dedupe).

## 4. How would you handle model routing across GPT-4 / Claude / local models?

Route by **capability + cost + health**:
- **Classify**: simple (math/lookup) vs complex (multi-step) using heuristics or a small classifier.
- **Select**: cheapest model that satisfies required features (tools, context, vision) and meets SLO.
- **Health**: provider score = P95 latency + error rate; route away when degraded.
- **Budgets**: per-user/org budgets; graceful downgrade to cheaper models.
- **Fallback**: retry once with a secondary provider on provider errors.

Implementation detail: keep a shared `LLMProviderInterface` so orchestration is provider-agnostic.

## 5. How would you sandbox potentially unsafe execution tools?

Tools that execute code, access the filesystem, or make network calls must be sandboxed to prevent security breaches.

Defense in depth:
- **Strict inputs**: allowlists + size limits; reject traversal/injection patterns.
- **Deterministic parsing**: AST-allowlist for expressions (no `eval()`).
- **Isolation** for risky tools:
  - ephemeral containers/microVMs (Firecracker), read-only FS, no secrets, cgroups limits, hard timeouts
  - network egress allowlist (or none)
  - seccomp/AppArmor/gVisor when needed
- **Output hygiene**: cap output size, normalize encoding, wrap tool output to reduce prompt injection.

## 6. How would you prevent recursive infinite agent loops?

Infinite loops occur when agents repeatedly delegate to each other or when tool calls trigger more tool calls endlessly.

Controls:
- **Max LLM round-trips** per request (e.g., 2–5).
- **Max tool calls** per turn + per request; timeout each tool call.
- **Depth limits** for delegation; stop delegating when depth exceeded.
- **Cycle detection**: `(agent_id, task_hash)` repeat → abort.
- **Budgets**: token/time budgets for the full request.
- **Retry caps**: provider retry once; tool retries capped; circuit breakers on repeated failure.

In this implementation specifically: tool calls per turn are capped and the orchestrator performs at most one follow-up LLM call after tools, so runaway loops are structurally constrained.
