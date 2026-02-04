from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastmcp import Client as MCPClient

from app.core.config import get_settings
from app.core.logging import configure_logging

from agent.llm_client import get_openai_client
from agent.mcp_bridge import (
    call_tool_safe,
    find_auth_me_tool_name,
    mcp_tool_to_openai_function_tool,
)
from agent.prompt import build_capabilities_text, build_system_prompt
from agent.guardrails import apply_tasks_due_on_override
from agent.responses_parse import decode_call_arguments, extract_function_calls, extract_output_text
from agent.reviewer import (
    as_assistant_tool_result_message,
    compact_evidence,
    extract_tool_results_from_messages,
    review_and_rewrite_final_answer,
    should_run_reviewer,
)

settings = get_settings()
configure_logging(settings.log_level)

MAX_STEPS = settings.agent_max_steps
MCP_HTTP_URL = settings.mcp_server_url

logger = logging.getLogger("agent.runtime")


def _is_capabilities_question(convo: List[Dict[str, Any]]) -> bool:
    """Detect if the last user message is asking about capabilities."""
    if not convo:
        return False
    last = convo[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return False
    content = (last.get("content") or "").strip().lower()
    return content in {
        "what can i do?",
        "what can i do",
        "help",
        "commands",
        "capabilities",
        "what are my permissions?",
        "what are my permissions",
    }


def _normalize_me_payload(raw: Any) -> Dict[str, Any]:
    """
    Normalize the auth_me tool result into:
      { user_id, permissions: [..], roles: [..], debug }
    Works across fastmcp result shapes.
    """
    data = getattr(raw, "data", None)
    if data is None:
        data = getattr(raw, "content", None)
    if data is None:
        data = raw

    # Sometimes tools return a list of "content parts" with {"text": "...json..."}
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            try:
                data = json.loads(first["text"])
            except Exception:
                data = first["text"]
        else:
            txt = getattr(first, "text", None)
            if isinstance(txt, str):
                try:
                    data = json.loads(txt)
                except Exception:
                    data = txt
            else:
                data = first

    # If wrapped in {"result": ...}
    if isinstance(data, dict) and "result" in data and isinstance(data["result"], (dict, list, str)):
        data = data["result"]

    # If it's JSON string
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return {"user_id": None, "permissions": [], "roles": [], "debug": {"parse": "not_json"}}

    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = data[0]

    if not isinstance(data, dict):
        return {"user_id": None, "permissions": [], "roles": [], "debug": {"parse": "not_dict"}}

    perms = data.get("permissions") or []
    if isinstance(perms, set):
        perms = sorted(perms)
    if not isinstance(perms, list):
        perms = []

    roles = data.get("roles") or []
    if isinstance(roles, set):
        roles = sorted(roles)
    if not isinstance(roles, list):
        roles = []

    return {
        "user_id": data.get("user_id"),
        "permissions": [str(p) for p in perms],
        "roles": [str(r) for r in roles],
        "debug": data.get("debug", None),
    }


async def _run_local_agent_async(
    jwt_token: str,
    agent_run_id: int,
    prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Run a local agent loop asynchronously."""
    oai = get_openai_client()
    mcp = MCPClient(MCP_HTTP_URL, auth=f"Bearer {jwt_token}")

    logger.info(
        "run=%s | start | MCP_HTTP_URL=%s | MAX_STEPS=%s",
        agent_run_id,
        MCP_HTTP_URL,
        MAX_STEPS,
    )

    async with mcp:
        mcp_tools = await mcp.list_tools()
        logger.info("run=%s | mcp.list_tools | count=%s", agent_run_id, len(mcp_tools))

        openai_tools = [mcp_tool_to_openai_function_tool(t) for t in mcp_tools]

        convo = (
            messages
            if (messages and isinstance(messages, list) and len(messages) > 0)
            else [{"role": "user", "content": prompt or ""}]
        )

        # ---- Permissions prefetch ----
        auth_me_name = find_auth_me_tool_name(mcp_tools)
        me_data: Dict[str, Any] = {"user_id": None, "permissions": [], "roles": [], "debug": None}
        perms_status = "ok"

        if not auth_me_name:
            perms_status = "no_auth_me_tool"
            logger.warning("run=%s | auth_me tool not found in list_tools()", agent_run_id)
        else:
            logger.info("run=%s | auth_me tool picked: %s", agent_run_id, auth_me_name)
            try:
                raw = await mcp.call_tool(
                    auth_me_name,
                    {"auth": f"Bearer {jwt_token}", "agent_run_id": agent_run_id},
                )
                me_data = _normalize_me_payload(raw)
            except Exception as e:
                perms_status = "auth_me_call_failed"
                me_data = {"user_id": None, "permissions": [], "roles": [], "debug": {"error": str(e)}}
                logger.exception("run=%s | auth_me call failed", agent_run_id)

        perms_list = me_data.get("permissions") or []
        roles_list = me_data.get("roles") or []
        if not isinstance(perms_list, list):
            perms_list = []
        if not isinstance(roles_list, list):
            roles_list = []

        capabilities_text = build_capabilities_text([str(x) for x in perms_list], perms_status)

        if _is_capabilities_question(convo):
            if perms_status != "ok":
                return (
                    "I can’t reliably determine your tool permissions right now "
                    f"(status: {perms_status}). Try again, or check the server logs."
                )
            return "Here’s what you can do with your current permissions:\n" + capabilities_text

        me_for_model = {
            "user_id": me_data.get("user_id"),
            "roles": roles_list,
            "permissions": perms_list,
        }

        system_content = build_system_prompt(
            perms_status=perms_status,
            me_for_model=me_for_model,
            capabilities_text=capabilities_text,
        )

        input_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}, *convo]

        for _step in range(MAX_STEPS):
            resp = oai.responses.create(
                model=settings.llm_model,
                input=input_messages,
                tools=openai_tools,
            )

            calls = extract_function_calls(resp)
            if calls:
                for call in calls:
                    name = str(call.get("name") or "")
                    args = decode_call_arguments(call.get("arguments"))

                    # tasks-only due_on override (does NOT touch weather)
                    args = apply_tasks_due_on_override(name, args, convo)

                    # Always attach auth + run id for MCP tools
                    args["auth"] = f"Bearer {jwt_token}"
                    args["agent_run_id"] = agent_run_id

                    log_args = dict(args)
                    if "auth" in log_args:
                        log_args["auth"] = "***redacted***"

                    logger.info(
                        "run=%s | tool_call | %s | args=%s",
                        agent_run_id,
                        name,
                        json.dumps(log_args, default=str),
                    )

                    payload = await call_tool_safe(mcp, name, args)
                    input_messages.append(as_assistant_tool_result_message(name, payload))

                continue

            text = extract_output_text(resp)
            if text:
                tool_results = extract_tool_results_from_messages(input_messages)
                if should_run_reviewer(tool_results):
                    evidence = compact_evidence(tool_results)
                    try:
                        reviewed = review_and_rewrite_final_answer(
                            oai,
                            model=settings.reviewer_model,
                            final_text=text,
                            evidence=evidence,
                        )
                        logger.info(
                            "run=%s | reviewer_applied | evidence_chars=%s | draft_chars=%s | final_chars=%s",
                            agent_run_id,
                            len(evidence),
                            len(text),
                            len(reviewed),
                        )
                        return reviewed
                    except Exception:
                        logger.exception("run=%s | reviewer failed", agent_run_id)
                        return text

                return text

            return "Model returned no text and no tool calls."

        return "Agent did not converge."


def run_agent(
    prompt: str,
    jwt_token: str,
    agent_run_id: int,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Run a local agent loop synchronously."""
    return asyncio.run(
        _run_local_agent_async(
            jwt_token=jwt_token,
            agent_run_id=agent_run_id,
            prompt=prompt,
            messages=messages,
        )
    )
