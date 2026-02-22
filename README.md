# RBAC MCP Agent Demo

A small full-stack demo application that shows how an **AI agent can safely call tools using Role-Based Access Control (RBAC)**.

The agent is powered by an LLM and integrates with **Model Context Protocol (MCP)** tools, but **every tool call is authorized against the current user’s permissions**.

This repository is intended as:

- a learning project
- a reference implementation
- a concrete example of permission-aware agents

---

## What This App Does

- Lets users log in with different roles
- Runs an AI agent that can:
  - reason about user prompts
  - decide which tools to call
  - execute MCP tools **only if the user is allowed**
- Records:
  - agent runs
  - tool calls
  - authorization decisions
- Supports:
  - permission request + approval workflow
  - role/permission assignment and user-role mapping
  - delegated “for others” permissions
  - notifications and event streaming
  - push-to-talk voice input with server-side transcription

In short: **the LLM can think freely, but it cannot act freely.**

<img src="./docs/rbac_login.png" width="800" />

## LLM Access

This demo **does not provide a shared LLM key**.

This demo uses a single backend-level `OPENAI_API_KEY` from `backend/.env`.

That means:

- there is no per-user API key entry in the UI
- the backend calls OpenAI directly for both agent responses and transcription
- without `OPENAI_API_KEY`, `/agent/run` and `/agent/transcribe` will fail

The key is still externalized via environment config (not hardcoded in source).

---

## What This App Is *Not*

This is **not**:

- a production-ready RBAC framework
- a general-purpose agent platform
- a secure enterprise auth solution
- a full MCP showcase
- optimized for scale or performance

It is intentionally small and explicit.

---

## Why RBAC + MCP for Agents?

Modern agent demos often assume:

> “If the agent can call the tool, it should.”

This app demonstrates the opposite:

- Tools exist independently of permissions
- Permissions are resolved **per user**
- The agent must respect those permissions at runtime
- Unauthorized tool calls are blocked and audited

This mirrors how **real internal tools** need to behave.

---

## Architecture (High-Level)

- **Frontend**: React UI for login, agent chat, trace inspection, and admin access management
- **Backend**: FastAPI API handling auth, RBAC, permission requests, notifications, and agent runs
- **Agent Runtime**:
  - LLM reasoning
  - Tool selection
  - MCP execution
  - Permission checks
- **MCP Server**:
  - Auth tools
  - Notes tools
  - Tasks tools
  - Weather tools
  - Alarm tools
  - Approval tools
  - Permission request tools
  - User lookup tools (for resolving account owners in delegated "on behalf of" actions)

All agent actions are logged for inspection.

<img src="./docs/rbac_agent.png" width="800" />

## Tech Stack

### Backend
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT authentication
- FastMCP
- OpenAI API

### Frontend
- React (Vite)
- TypeScript
- Mantine UI
- Axios
- React Router

---

## Setup: Environment Variables

Create a `.env` file in the `backend/` directory with:

```env
# Required for startup
DATABASE_URL=postgresql+psycopg2://postgres:your-password@localhost:5432/rbac_mcp_app

# Required for /agent/run and /agent/transcribe
OPENAI_API_KEY=your-openai-api-key-here

# Optional
MCP_SERVER_URL=http://127.0.0.1:8001/mcp
LLM_MODEL=gpt-4.1-mini
REVIEWER_MODEL=gpt-4.1-mini
TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe

# Optional runtime/config
APP_TIMEZONE=UTC
LOG_LEVEL=INFO
LOG_FORMAT=text
LOG_REDACT_FIELDS=password,token,secret,authorization,api_key,openai_api_key,jwt_secret
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
LOGIN_RATE_LIMIT_ATTEMPTS=10
LOGIN_RATE_LIMIT_WINDOW_SECONDS=60
SSE_CONNECT_RATE_LIMIT_ATTEMPTS=30
SSE_CONNECT_RATE_LIMIT_WINDOW_SECONDS=60
# defaults to false in prod, true otherwise
SSE_ALLOW_QUERY_TOKEN=true
MCP_HOST=0.0.0.0
MCP_PORT=8001
AGENT_MAX_STEPS=8
JWT_SECRET=change-me-in-non-dev
JWT_EXP_HOURS=24
APP_ENV=dev

# Database pool + timeout tuning
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT_SECONDS=30
DB_POOL_RECYCLE_SECONDS=1800
DB_CONNECT_TIMEOUT_SECONDS=10
DB_STATEMENT_TIMEOUT_MS=15000
DB_LOCK_TIMEOUT_MS=5000
DB_IDLE_TX_TIMEOUT_MS=30000
```

Frontend optional variable (`frontend/.env.local`):

```env
VITE_API_BASE_URL=http://localhost:8000
```

The backend also supports speech-to-text at `/agent/transcribe` (used by hold-to-talk in the agent page), with model controlled by `TRANSCRIPTION_MODEL`.

Additional implemented backend capabilities include:
- conversation lifecycle APIs (`/agent/conversations`, `/agent/conversations/{id}`, `/agent/conversations/approvals`)
- user timezone APIs (`/timezones`, `/me/timezone`)
- notification SSE stream (`/api/events/stream`)
- token-usage summaries returned in `/me` and conversation list responses
- health/readiness/ops endpoints (`/healthz`, `/readyz`, `/metrics/runtime`)

Note: `DATABASE_URL` is required for both the API server and MCP server startup. The app currently expects PostgreSQL.

Get an API key from [OpenAI](https://platform.openai.com/api-keys).

---

## Roles & Permissions (Demo Setup)

On first run, the database is seeded with demo users:

| User | Password | Role | Can Do |
|-----|------|------|--------|
| alice@example.com | password | basic | Weather, notes, notifications, request permissions |
| bob@example.com | password | pro | Basic + tasks, alarms, "for others" actions |
| admin@example.com | admin | admin | All tools + approve requests + full trace visibility |

The same agent behaves differently depending on who is logged in.

Note: delegation requests can also be approved/rejected by the target user (the account owner), not only by admins.

---

## Running the App

### Backend API
```
cd backend
python -m venv venv
# Windows PowerShell:
./venv/Scripts/Activate.ps1
# macOS/Linux:
# source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs at: `http://localhost:8000`

### MCP server (separate terminal)
```
cd backend
# Windows PowerShell:
./venv/Scripts/Activate.ps1
python -m mcp_app.server
```

Runs at: `http://localhost:8001/mcp`

### Frontend
```
cd frontend
npm install
npm run dev
```

Runs at: `http://localhost:5173`

For hold-to-talk voice input, allow microphone permission in your browser.

### PostgreSQL setup (required)
The backend currently requires PostgreSQL via `DATABASE_URL`.

After PostgreSQL is installed locally:

1) Create the database (PowerShell example):
```powershell
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE rbac_mcp_app;"
```

2) Set `DATABASE_URL` in `backend/.env`:
```env
DATABASE_URL=postgresql+psycopg2://postgres:your-password@localhost:5432/rbac_mcp_app
```

3) Install dependencies and run migrations (recommended):
```powershell
cd backend
./venv/Scripts/Activate.ps1
pip install -r requirements.txt
alembic upgrade head
```

If you skip Alembic, the API startup still creates tables from SQLAlchemy models (`Base.metadata.create_all`), but migrations are recommended for consistency.

4) Start/restart backend API + MCP server so `LISTEN/NOTIFY` event forwarding is active.

## Voice Input
- The agent page supports hold-to-talk recording in the browser.
- Audio is posted to `POST /agent/transcribe` and appended to the prompt.
- Optional toggle: auto-run immediately after transcription.
- Current backend payload limit for transcription audio is 3 MB.

## Design Notes
- RBAC is enforced outside the LLM
- The agent never decides what it is allowed to do
- MCP tools are unaware of user identity
- Authorization happens at the orchestration layer
- Audit logs and notifications are treated as first-class data
- SSE is used for near-real-time notification updates

## Realtime Signaling (SSE, Postgres, Redis)
- Browser updates are delivered via SSE (`/api/events/stream`).
- Notifications are always stored durably in the database, then pushed to connected clients.
- With PostgreSQL, the app uses `LISTEN/NOTIFY` for cross-process event signaling (API + MCP server).
- This is a strong default for demo/small deployments (for example, a few to low-hundreds concurrent SSE clients with modest event volume).
- If deployment grows (higher fanout, higher events/sec, multiple app nodes, rising realtime latency), move signaling to Redis pub/sub (or another dedicated broker) while keeping the database as the source of truth.
- SSE auth prefers `Authorization: Bearer <token>`; query-token auth is deprecated and controlled by `SSE_ALLOW_QUERY_TOKEN` (enabled by default outside prod, disabled by default in prod).
- Each SSE connection is intentionally recycled after ~5 minutes (`SSE_MAX_STREAM_SECONDS=300`), so clients should auto-reconnect.

## Logging and Redaction
- Default log format is text. Set `LOG_FORMAT=json` for structured logs.
- Request correlation is propagated with `X-Request-ID` (generated if missing).
- Sensitive values are redacted using `LOG_REDACT_FIELDS` across log message args.
- Built-in masking also redacts bearer tokens, JWT-like values, and obscures email local parts.

## Health, Readiness, and Runtime Metrics
- `GET /healthz`: liveness and runtime lifecycle state.
- `GET /readyz`: readiness check (returns `503` during shutdown or when DB is unavailable).
- `GET /metrics/runtime`: startup/shutdown counters and latest shutdown duration (requires auth + `agent:trace:view_all`).

## Notes on Defaults
- In development, `JWT_SECRET` defaults to `dev-secret`; set an explicit strong value for non-dev environments.
- In production (`APP_ENV=prod|production`), startup fails if `JWT_SECRET` is left as the default.

## Retry Policy (Operational Guidance)
- Database reliability: connection pool pre-ping is enabled; keep statement/lock/idle transaction timeouts conservative.
- API clients (frontend/integration): retry only idempotent requests (`GET`, safe reads), using bounded exponential backoff with jitter.
- Do not blindly retry mutating endpoints (`POST`, `PUT`, `DELETE`) unless you implement idempotency keys.
- Treat `429` and transient `5xx` as retryable; do not retry auth/permission denials (`401`, `403`) without user action.
- `POST /login` and `GET /api/events/stream` include in-memory rate limiting and may return `429` with `Retry-After`.
- Current limiter state is per-process (single-node friendly, not shared across multiple app instances).

## Who This Is For
- Developers experimenting with agent tooling
- Anyone curious about MCP + permissions
- Teams thinking about safe internal AI agents
- People tired of “unrestricted agent” demos

## License
MIT