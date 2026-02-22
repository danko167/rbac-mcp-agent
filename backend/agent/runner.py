from __future__ import annotations

import json
import logging
import re
import ast
from dataclasses import dataclass
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
from agent.intents import (
    is_alarm_cancel_intent,
    is_alarm_set_intent,
    is_alarm_show_intent,
    is_capabilities_question,
)
from agent.responses_parse import decode_call_arguments, extract_function_calls, extract_output_text
from agent.tool_grounding import latest_success_result, mutation_success_text, summarize_alarms_for_user
from agent.reviewer import (
    as_assistant_tool_result_message,
    compact_evidence,
    extract_tool_results_from_messages,
    review_and_rewrite_final_answer,
    should_run_reviewer,
)
from agent.specialists import filter_tools_for_profile, is_tool_allowed, route_agent_profile
from app.services.token_usage import extract_openai_usage

settings = get_settings()
configure_logging(settings.log_level)

MAX_STEPS = max(settings.agent_max_steps, 1)
MCP_HTTP_URL = settings.mcp_server_url

logger = logging.getLogger("agent.runner")


@dataclass
class AgentRunResult:
    text: str
    usage: dict[str, int]


def _empty_usage() -> dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _merge_usage(target: dict[str, int], source: dict[str, int]) -> None:
    target["input_tokens"] += int(source.get("input_tokens", 0) or 0)
    target["output_tokens"] += int(source.get("output_tokens", 0) or 0)
    target["total_tokens"] += int(source.get("total_tokens", 0) or 0)


def _normalize_me_payload(raw: Any) -> Dict[str, Any]:
    data = raw

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


def _latest_user_text(convo: List[Dict[str, Any]]) -> str:
    for message in reversed(convo):
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content") or "").strip()
    return ""


def _extract_alarm_title(text: str) -> str | None:
    quoted = re.search(r'["“](.+?)["”]', text)
    if quoted and quoted.group(1).strip():
        return quoted.group(1).strip()

    titled = re.search(r"\btitle\s+(?:is\s+)?(.+)$", text, flags=re.IGNORECASE)
    if titled and titled.group(1).strip():
        candidate = titled.group(1).strip().strip(".?!")
        return candidate or None

    named = re.search(r"\bnamed\s+(.+)$", text, flags=re.IGNORECASE)
    if named and named.group(1).strip():
        candidate = named.group(1).strip().strip(".?!")
        return candidate or None

    return None


def _extract_alarm_time_phrase(text: str) -> str | None:
    relative = re.search(
        r"\b(?:in\s+)?\d+\s*(?:seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\s*(?:from\s+now)?\b",
        text,
        flags=re.IGNORECASE,
    )
    if relative:
        return relative.group(0).strip()

    iso_like = re.search(r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?\b", text)
    if iso_like:
        return iso_like.group(0).replace(" ", "T")

    return None


def _extract_target_hint(text: str) -> str | None:
    match = re.search(r"\bfor\s+([A-Za-z0-9._%+-]+(?:\s+[A-Za-z0-9._%+-]+)?)", text)
    if not match:
        return None
    hint = match.group(1).strip().strip(".?!")
    low = hint.lower()
    if low in {"me", "myself", "my"}:
        return None
    return hint


def _is_affirmative_alarm_cancel(convo: List[Dict[str, Any]]) -> bool:
    if not convo:
        return False

    last = convo[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return False

    last_text = str(last.get("content") or "").strip().lower()
    affirmative_tokens = {
        "yes",
        "y",
        "yep",
        "yeah",
        "sure",
        "ok",
        "okay",
        "do it",
        "please do",
    }
    if last_text not in affirmative_tokens:
        return False

    for message in reversed(convo[:-1]):
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "").strip().lower()
        if not content:
            continue
        if "alarm" in content and "cancel" in content:
            return True

    return False


def _alarm_rows_from_result(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, str):
        raw = result.strip()
        if raw:
            try:
                decoded = json.loads(raw)
            except Exception:
                try:
                    decoded = ast.literal_eval(raw)
                except Exception:
                    decoded = None
            if isinstance(decoded, list):
                return [item for item in decoded if isinstance(item, dict)]
    if isinstance(result, dict):
        if isinstance(result.get("id"), int) and (
            isinstance(result.get("title"), str)
            or isinstance(result.get("fire_at"), str)
            or isinstance(result.get("fire_at_local"), str)
        ):
            return [result]
        nested = result.get("result")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, str):
            return _alarm_rows_from_result(nested)
    return []


def _dict_rows_from_result(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        if isinstance(result.get("id"), int):
            return [result]
        nested = result.get("result")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            return [nested]
    return []


def _has_successful_tool_result(tool_results: List[Dict[str, Any]], tool_name: str) -> bool:
    expected = tool_name.strip().replace(".", "_").lower()
    for tool_result in tool_results:
        if tool_result.get("ok") is not True:
            continue
        current = str(tool_result.get("tool") or "").strip().replace(".", "_").lower()
        if current == expected:
            return True
    return False


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _required_tools_for_turn(convo: List[Dict[str, Any]]) -> set[str]:
    text = _latest_user_text(convo).lower()
    required: set[str] = set()

    if not text:
        return required

    if "alarm" in text:
        if _contains_any(text, ("show", "list", "what", "which", "have", "active", "upcoming")):
            required.add("alarms_list")
        if _contains_any(text, ("set", "create", "add", "schedule", "remind")):
            required.add("alarms_set")
        if _contains_any(text, ("cancel", "stop", "delete", "remove")):
            required.add("alarms_cancel")

    if _contains_any(text, ("note", "notes")):
        if _contains_any(text, ("show", "list", "what", "which", "have", "all")):
            required.add("notes_list")
        if _contains_any(text, ("create", "add", "new")):
            required.add("notes_create")
        if _contains_any(text, ("update", "edit", "change", "rename")):
            required.add("notes_update")
        if _contains_any(text, ("delete", "remove")):
            required.add("notes_delete")

    if _contains_any(text, ("task", "tasks", "todo")):
        if _contains_any(text, ("show", "list", "what", "which", "have", "all")):
            required.add("tasks_list")
        if _contains_any(text, ("create", "add", "new")):
            required.add("tasks_create")
        if _contains_any(text, ("update", "edit", "change", "rename", "reschedule")):
            required.add("tasks_update")
        if _contains_any(text, ("complete", "done", "finish")):
            required.add("tasks_complete")
        if _contains_any(text, ("delete", "remove")):
            required.add("tasks_delete")

    return required


def _missing_required_tools(tool_results: List[Dict[str, Any]], required_tools: set[str]) -> set[str]:
    missing: set[str] = set()
    for required_tool in required_tools:
        if not _has_successful_tool_result(tool_results, required_tool):
            missing.add(required_tool)
    return missing


async def run_local_agent_async(
    jwt_token: str,
    agent_run_id: int,
    prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> AgentRunResult:
    oai = get_openai_client()
    mcp = MCPClient(MCP_HTTP_URL, auth=f"Bearer {jwt_token}")

    logger.info(
        "run=%s | start | MCP_HTTP_URL=%s | MAX_STEPS=%s",
        agent_run_id,
        MCP_HTTP_URL,
        MAX_STEPS,
    )
    usage_totals = _empty_usage()

    def capture_usage(resp: Any) -> None:
        _merge_usage(usage_totals, extract_openai_usage(resp))

    async with mcp:
        mcp_tools = await mcp.list_tools()
        logger.info("run=%s | mcp.list_tools | count=%s", agent_run_id, len(mcp_tools))

        convo = (
            messages
            if (messages and isinstance(messages, list) and len(messages) > 0)
            else [{"role": "user", "content": prompt or ""}]
        )

        profile = route_agent_profile(convo)
        scoped_tools = filter_tools_for_profile(mcp_tools, profile)
        if not scoped_tools:
            scoped_tools = list(mcp_tools)

        logger.info(
            "run=%s | specialist=%s | scoped_tool_count=%s",
            agent_run_id,
            profile.key,
            len(scoped_tools),
        )

        openai_tools = [mcp_tool_to_openai_function_tool(t) for t in scoped_tools]

        auth_me_name = find_auth_me_tool_name(mcp_tools)
        me_data: Dict[str, Any] = {"user_id": None, "permissions": [], "roles": [], "debug": None}
        perms_status = "ok"

        if not auth_me_name:
            perms_status = "no_auth_me_tool"
            logger.warning("run=%s | auth_me tool not found in list_tools()", agent_run_id)
        else:
            logger.info("run=%s | auth_me tool picked: %s", agent_run_id, auth_me_name)
            payload = await call_tool_safe(
                mcp,
                auth_me_name,
                {"auth": f"Bearer {jwt_token}", "agent_run_id": agent_run_id},
            )
            if payload.get("ok") is True:
                me_data = _normalize_me_payload(payload.get("result"))
            else:
                perms_status = "auth_me_call_failed"
                me_data = {
                    "user_id": None,
                    "permissions": [],
                    "roles": [],
                    "debug": {"error": payload.get("error")},
                }
                logger.warning("run=%s | auth_me call failed: %s", agent_run_id, payload.get("error"))

        perms_list = me_data.get("permissions") or []
        roles_list = me_data.get("roles") or []
        if not isinstance(perms_list, list):
            perms_list = []
        if not isinstance(roles_list, list):
            roles_list = []

        capabilities_text = build_capabilities_text([str(x) for x in perms_list], perms_status)

        if is_capabilities_question(convo):
            if perms_status != "ok":
                return AgentRunResult(
                    text=(
                        "I can’t reliably determine your tool permissions right now "
                        f"(status: {perms_status}). Try again, or check the server logs."
                    ),
                    usage=usage_totals,
                )
            return AgentRunResult(
                text="Here’s what you can do with your current permissions:\n" + capabilities_text,
                usage=usage_totals,
            )

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
        system_content = (
            system_content
            + "\n\nSPECIALIST MODE:\n"
            + f"{profile.name}\n"
            + f"{profile.instruction}\n"
        )

        input_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}, *convo]
        cancel_succeeded_in_run = False

        for _step in range(MAX_STEPS):
            resp = oai.responses.create(
                model=settings.llm_model,
                input=input_messages,
                tools=openai_tools,
            )
            capture_usage(resp)

            calls = extract_function_calls(resp)
            if calls:
                for call in calls:
                    name = str(call.get("name") or "")
                    args = decode_call_arguments(call.get("arguments"))
                    normalized_name = name.strip().replace(".", "_").lower()

                    if normalized_name == "alarms_set" and args.get("target_user_id") is None:
                        latest_text = _latest_user_text(convo)
                        target_hint = _extract_target_hint(latest_text)
                        if target_hint:
                            users_payload = await call_tool_safe(
                                mcp,
                                "users_list",
                                {
                                    "auth": f"Bearer {jwt_token}",
                                    "agent_run_id": agent_run_id,
                                    "query": target_hint,
                                },
                            )
                            if users_payload.get("ok") is not True:
                                payload = {
                                    "ok": False,
                                    "error": f"Could not resolve target user '{target_hint}' before setting alarm.",
                                }
                                input_messages.append(as_assistant_tool_result_message(name, payload))
                                continue

                            users = _dict_rows_from_result(users_payload.get("result"))
                            exact = next(
                                (
                                    item for item in users
                                    if str(item.get("email") or "").lower().startswith(target_hint.lower())
                                    or str(item.get("email") or "").lower() == target_hint.lower()
                                ),
                                None,
                            )
                            if not exact and users:
                                exact = users[0]

                            if isinstance(exact, dict) and isinstance(exact.get("id"), int):
                                args["target_user_id"] = int(exact["id"])
                            else:
                                payload = {
                                    "ok": False,
                                    "error": f"Could not resolve target user '{target_hint}' before setting alarm.",
                                }
                                input_messages.append(as_assistant_tool_result_message(name, payload))
                                continue

                    if normalized_name == "alarms_cancel" and cancel_succeeded_in_run:
                        payload = {
                            "ok": True,
                            "result": {
                                "ok": True,
                                "already_cancelled_this_run": True,
                            },
                        }
                        input_messages.append(as_assistant_tool_result_message(name, payload))
                        continue

                    if not is_tool_allowed(profile, name):
                        payload = {
                            "ok": False,
                            "error": (
                                f"Tool '{name}' is outside the active specialist scope ({profile.name})."
                            ),
                        }
                        input_messages.append(as_assistant_tool_result_message(name, payload))
                        continue

                    args = apply_tasks_due_on_override(name, args, convo)

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
                    if normalized_name == "alarms_cancel" and payload.get("ok") is True:
                        cancel_succeeded_in_run = True
                    input_messages.append(as_assistant_tool_result_message(name, payload))

                continue

            text = extract_output_text(resp)
            if text:
                tool_results = extract_tool_results_from_messages(input_messages)
                required_tools = _required_tools_for_turn(convo)

                if "notes_list" in required_tools and not _has_successful_tool_result(tool_results, "notes_list"):
                    listed_notes = await call_tool_safe(
                        mcp,
                        "notes_list",
                        {"auth": f"Bearer {jwt_token}", "agent_run_id": agent_run_id},
                    )
                    if listed_notes.get("ok") is True and isinstance(listed_notes.get("result"), list):
                        notes_rows = [item for item in listed_notes.get("result") if isinstance(item, dict)]
                        if not notes_rows:
                            return AgentRunResult(text="You currently have no notes.", usage=usage_totals)
                        if len(notes_rows) == 1:
                            one = notes_rows[0]
                            title = one.get("title")
                            if isinstance(title, str) and title.strip():
                                return AgentRunResult(text=f'You have one note titled "{title}".', usage=usage_totals)
                        return AgentRunResult(text=f"You currently have {len(notes_rows)} notes.", usage=usage_totals)

                if "tasks_list" in required_tools and not _has_successful_tool_result(tool_results, "tasks_list"):
                    listed_tasks = await call_tool_safe(
                        mcp,
                        "tasks_list",
                        {"auth": f"Bearer {jwt_token}", "agent_run_id": agent_run_id},
                    )
                    if listed_tasks.get("ok") is True and isinstance(listed_tasks.get("result"), list):
                        task_rows = [item for item in listed_tasks.get("result") if isinstance(item, dict)]
                        if not task_rows:
                            return AgentRunResult(text="You currently have no tasks.", usage=usage_totals)
                        if len(task_rows) == 1:
                            one = task_rows[0]
                            title = one.get("title")
                            if isinstance(title, str) and title.strip():
                                return AgentRunResult(text=f'You have one task titled "{title}".', usage=usage_totals)
                        return AgentRunResult(text=f"You currently have {len(task_rows)} tasks.", usage=usage_totals)

                if is_alarm_show_intent(convo):
                    listed = await call_tool_safe(
                        mcp,
                        "alarms_list",
                        {"auth": f"Bearer {jwt_token}", "agent_run_id": agent_run_id},
                    )
                    if listed.get("ok") is not True:
                        error_text = listed.get("error")
                        if isinstance(error_text, str) and error_text.strip():
                            return AgentRunResult(text=f"I couldn't list alarms: {error_text}", usage=usage_totals)
                        return AgentRunResult(text="I couldn't list alarms right now.", usage=usage_totals)

                    alarms = _alarm_rows_from_result(listed.get("result"))
                    return AgentRunResult(text=summarize_alarms_for_user(alarms), usage=usage_totals)

                should_deterministic_cancel = is_alarm_cancel_intent(convo) or _is_affirmative_alarm_cancel(convo)
                if should_deterministic_cancel:
                    if _has_successful_tool_result(tool_results, "alarms_cancel"):
                        mutation_text = mutation_success_text(tool_results)
                        if mutation_text:
                            return AgentRunResult(text=mutation_text, usage=usage_totals)

                    listed = await call_tool_safe(
                        mcp,
                        "alarms_list",
                        {"auth": f"Bearer {jwt_token}", "agent_run_id": agent_run_id},
                    )
                    if listed.get("ok") is not True:
                        error_text = listed.get("error")
                        if isinstance(error_text, str) and error_text.strip():
                            return AgentRunResult(text=f"I couldn't list alarms for cancellation: {error_text}", usage=usage_totals)
                        return AgentRunResult(text="I couldn't list alarms for cancellation right now.", usage=usage_totals)

                    alarms = _alarm_rows_from_result(listed.get("result"))
                    if not alarms:
                        return AgentRunResult(text="You currently have no active alarms to cancel.", usage=usage_totals)

                    if len(alarms) == 1 and isinstance(alarms[0].get("id"), int):
                        cancel_payload = await call_tool_safe(
                            mcp,
                            "alarms_cancel",
                            {
                                "auth": f"Bearer {jwt_token}",
                                "agent_run_id": agent_run_id,
                                "alarm_id": int(alarms[0]["id"]),
                            },
                        )
                        if cancel_payload.get("ok") is True:
                            title = alarms[0].get("title")
                            if isinstance(title, str) and title.strip():
                                return AgentRunResult(text=f'Cancelled alarm "{title}".', usage=usage_totals)
                            return AgentRunResult(text="Cancelled the alarm.", usage=usage_totals)

                        error_text = cancel_payload.get("error")
                        if isinstance(error_text, str) and error_text.strip():
                            return AgentRunResult(text=f"I couldn't cancel the alarm: {error_text}", usage=usage_totals)
                        return AgentRunResult(text="I couldn't cancel the alarm.", usage=usage_totals)

                    return AgentRunResult(
                        text="I found multiple active alarms. Tell me which one to cancel (first/second or title).",
                        usage=usage_totals,
                    )

                mutation_text = mutation_success_text(tool_results)
                if mutation_text:
                    return AgentRunResult(text=mutation_text, usage=usage_totals)

                should_deterministic_alarm_set = (
                    is_alarm_set_intent(convo)
                    and not _has_successful_tool_result(tool_results, "alarms_set")
                )
                if should_deterministic_alarm_set:
                    latest_text = _latest_user_text(convo)
                    title = _extract_alarm_title(latest_text)
                    fire_at = _extract_alarm_time_phrase(latest_text)

                    if not title:
                        return AgentRunResult(
                            text="I can set that, but I need an alarm title. What should I call it?",
                            usage=usage_totals,
                        )
                    if not fire_at:
                        return AgentRunResult(
                            text="I can set that, but I need the time. Tell me when it should fire.",
                            usage=usage_totals,
                        )

                    target_user_id: int | None = None
                    target_hint = _extract_target_hint(latest_text)
                    if target_hint:
                        users_payload = await call_tool_safe(
                            mcp,
                            "users_list",
                            {
                                "auth": f"Bearer {jwt_token}",
                                "agent_run_id": agent_run_id,
                                "query": target_hint,
                            },
                        )
                        users = _dict_rows_from_result(users_payload.get("result"))
                        exact = next(
                            (
                                item for item in users
                                if str(item.get("email") or "").lower().startswith(target_hint.lower())
                                or str(item.get("email") or "").lower() == target_hint.lower()
                            ),
                            None,
                        )
                        if not exact and users:
                            exact = users[0]
                        if isinstance(exact, dict) and isinstance(exact.get("id"), int):
                            target_user_id = int(exact["id"])
                        else:
                            return AgentRunResult(
                                text=f"I couldn't find a user match for '{target_hint}'. Please provide the exact email.",
                                usage=usage_totals,
                            )

                    set_args: Dict[str, Any] = {
                        "auth": f"Bearer {jwt_token}",
                        "agent_run_id": agent_run_id,
                        "title": title,
                        "fire_at": fire_at,
                    }
                    if target_user_id is not None:
                        set_args["target_user_id"] = target_user_id

                    set_payload = await call_tool_safe(mcp, "alarms_set", set_args)
                    if set_payload.get("ok") is True and isinstance(set_payload.get("result"), dict):
                        result = set_payload["result"]
                        result_title = result.get("title")
                        result_time = result.get("fire_at_local") or result.get("fire_at")
                        if isinstance(result_title, str) and isinstance(result_time, str):
                            return AgentRunResult(text=f'Alarm set: "{result_title}" at {result_time}.', usage=usage_totals)
                        return AgentRunResult(text="Alarm set successfully.", usage=usage_totals)

                    error_text = set_payload.get("error") if isinstance(set_payload, dict) else None
                    if isinstance(error_text, str) and error_text.strip():
                        return AgentRunResult(text=f"I couldn't set the alarm: {error_text}", usage=usage_totals)

                    return AgentRunResult(
                        text="I couldn't confirm that the alarm was created because the alarm tool did not return a valid result.",
                        usage=usage_totals,
                    )

                missing_required = _missing_required_tools(tool_results, required_tools)
                if missing_required:
                    missing_sorted = ", ".join(sorted(missing_required))
                    return AgentRunResult(
                        text=(
                            "I couldn't complete that action because the required tool step did not run successfully "
                            f"({missing_sorted}). Please rephrase with explicit details and I'll execute it deterministically."
                        ),
                        usage=usage_totals,
                    )

                if should_run_reviewer(tool_results):
                    evidence = compact_evidence(tool_results)
                    try:
                        reviewed = review_and_rewrite_final_answer(
                            oai,
                            model=settings.reviewer_model,
                            final_text=text,
                            evidence=evidence,
                            on_response=capture_usage,
                        )
                        logger.info(
                            "run=%s | reviewer_applied | evidence_chars=%s | draft_chars=%s | final_chars=%s",
                            agent_run_id,
                            len(evidence),
                            len(text),
                            len(reviewed),
                        )
                        return AgentRunResult(text=reviewed, usage=usage_totals)
                    except Exception:
                        logger.exception("run=%s | reviewer failed", agent_run_id)
                        return AgentRunResult(text=text, usage=usage_totals)

                return AgentRunResult(text=text, usage=usage_totals)

            return AgentRunResult(text="Model returned no text and no tool calls.", usage=usage_totals)

        tool_results = extract_tool_results_from_messages(input_messages)
        if tool_results:
            evidence = compact_evidence(tool_results)
            try:
                recovered = review_and_rewrite_final_answer(
                    oai,
                    model=settings.reviewer_model,
                    final_text=(
                        "The assistant reached step limit. Provide the best final response based only on tool evidence. "
                        "If action is incomplete, ask one precise follow-up question."
                    ),
                    evidence=evidence,
                    on_response=capture_usage,
                )
                if recovered:
                    logger.warning("run=%s | recovered_after_nonconvergence", agent_run_id)
                    return AgentRunResult(text=recovered, usage=usage_totals)
            except Exception:
                logger.exception("run=%s | nonconvergence recovery failed", agent_run_id)

        return AgentRunResult(text="Agent did not converge.", usage=usage_totals)
