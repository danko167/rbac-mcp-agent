from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from agent.runner import AgentRunResult, run_local_agent_async


def run_agent(
    prompt: str,
    jwt_token: str,
    agent_run_id: int,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> AgentRunResult:
    """Run a local agent loop synchronously."""
    return asyncio.run(
        run_local_agent_async(
            jwt_token=jwt_token,
            agent_run_id=agent_run_id,
            prompt=prompt,
            messages=messages,
        )
    )
