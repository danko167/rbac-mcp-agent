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

In short: **the LLM can think freely, but it cannot act freely.**

---

## LLM Access

This demo **does not provide a shared LLM key**.

Each user must supply **their own OpenAI-compatible API key**, which is used by the agent at runtime.

This keeps the demo:

- simple (no key management UI)
- transparent (no hidden proxying)
- closer to how internal tools often work

The backend only orchestrates agent logic and permissions — **it does not resell or manage LLM access**.

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

- **Frontend**: React UI for login, agent chat, and trace inspection
- **Backend**: FastAPI API handling auth, RBAC, and agent runs
- **Agent Runtime**:
  - LLM reasoning
  - Tool selection
  - MCP execution
  - Permission checks
- **MCP Server**:
  - Notes tools
  - Tasks tools
  - Weather tools

All agent actions are logged for inspection.

---

## Tech Stack

### Backend
- FastAPI
- SQLAlchemy
- SQLite
- JWT authentication
- FastMCP
- OpenAI-compatible LLM API

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
OPENAI_API_KEY=your-openai-api-key-here
```

Get an API key from [OpenAI](https://platform.openai.com/api-keys) or any OpenAI-compatible provider.

---

## Roles & Permissions (Demo Setup)

On first run, the database is seeded with demo users:

| User | Role | Can Do |
|-----|------|--------|
| alice@example.com | basic | Weather, manage notes |
| bob@example.com | pro | Weather, notes, tasks |
| admin@example.com | admin | All tools + view all traces |

The same agent behaves differently depending on who is logged in.

---

## Running the App

### Backend
```
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs at: `http://localhost:8000`

Start the MCP server separately:
`python -m mcp_app.server`

Runs at: `http://localhost:8001/mcp`

### Frontend
```
cd frontend
npm install
npm run dev
```

Runs at: `http://localhost:5173`

## Design Notes
- RBAC is enforced outside the LLM
- The agent never decides what it is allowed to do
- MCP tools are unaware of user identity
- Authorization happens at the orchestration layer
- Audit logs are treated as first-class data
- This keeps concerns clean and observable.

## Who This Is For
- Developers experimenting with agent tooling
- Anyone curious about MCP + permissions
- Teams thinking about safe internal AI agents
- People tired of “unrestricted agent” demos

## License
MIT