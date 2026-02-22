from __future__ import annotations


def _to_title_case(input_value: str) -> str:
    parts = []
    for raw in input_value.replace("-", " ").replace("_", " ").replace(".", " ").split(" "):
        value = raw.strip()
        if value:
            parts.append(value[0].upper() + value[1:])
    return " ".join(parts)


KNOWN_PERMISSION_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "weather:read": {
        "title": "View weather information",
        "description": "Can check weather details in the app.",
    },
    "notes:list": {
        "title": "View your notes",
        "description": "Can see your personal notes.",
    },
    "notes:create": {
        "title": "Create your notes",
        "description": "Can add new notes for yourself.",
    },
    "notes:update": {
        "title": "Edit your notes",
        "description": "Can update notes you own.",
    },
    "notes:delete": {
        "title": "Delete your notes",
        "description": "Can remove notes you own.",
    },
    "notifications:list": {
        "title": "View notifications",
        "description": "Can read your notifications.",
    },
    "permissions:request": {
        "title": "Request more access",
        "description": "Can send permission access requests for approval.",
    },
    "permissions:approve": {
        "title": "Approve access requests",
        "description": "Can approve or reject permission requests from users.",
    },
    "tasks:receive": {
        "title": "Receive task assignments",
        "description": "Can receive tasks assigned by others.",
    },
    "tasks:list": {
        "title": "View your tasks",
        "description": "Can see task items you can work on.",
    },
    "tasks:create": {
        "title": "Create your tasks",
        "description": "Can create tasks for yourself.",
    },
    "tasks:update": {
        "title": "Edit your tasks",
        "description": "Can update task details.",
    },
    "tasks:complete": {
        "title": "Complete tasks",
        "description": "Can mark tasks as completed.",
    },
    "tasks:delete": {
        "title": "Delete tasks",
        "description": "Can remove task items.",
    },
    "tasks:create.for_others": {
        "title": "Create tasks for other users",
        "description": "Can create and assign tasks on behalf of others.",
    },
    "notes:create.for_others": {
        "title": "Create notes for other users",
        "description": "Can add notes on behalf of other users.",
    },
    "alarms:receive": {
        "title": "Receive alarms",
        "description": "Can receive alarm notifications.",
    },
    "alarms:set": {
        "title": "Set alarms",
        "description": "Can create alarms for yourself.",
    },
    "alarms:set.for_others": {
        "title": "Set alarms for other users",
        "description": "Can create alarms on behalf of other users.",
    },
    "agent:trace:view_all": {
        "title": "View all agent traces",
        "description": "Can inspect trace logs across users.",
    },
}


USER_FEATURE_TOOLS = {"alarms", "notes", "tasks", "weather"}
SYSTEM_ACCESS_TOOLS = {"permissions", "notifications", "agent"}


def get_permission_tool(permission: str) -> str:
    return (permission.split(":", 1)[0] or "other").strip() or "other"


def get_permission_category_from_tool(tool: str) -> str:
    if tool in USER_FEATURE_TOOLS:
        return "user_features"
    if tool in SYSTEM_ACCESS_TOOLS:
        return "system_access"
    return "other"


def get_permission_category_label(category: str) -> str:
    if category == "user_features":
        return "What You Can Use"
    if category == "system_access":
        return "System & Admin Access"
    return "Other Access"


def format_permission_tool_label(tool: str) -> str:
    return _to_title_case(tool)


def describe_permission(permission: str) -> dict[str, str]:
    known = KNOWN_PERMISSION_DESCRIPTIONS.get(permission)
    if known:
        return known

    resource, action = (permission.split(":", 1) + ["access"])[:2]
    resource = (resource or "resource").strip() or "resource"
    action = (action or "access").strip() or "access"

    for_others = action.endswith(".for_others")
    base_action = action.replace(".for_others", "") if for_others else action

    title = f"{_to_title_case(base_action)} {_to_title_case(resource)}"
    if for_others:
        description = f"Can {base_action.replace('_', ' ')} {resource} for other users."
    else:
        description = f"Can {base_action.replace('_', ' ')} {resource}."

    return {
        "title": title,
        "description": description,
    }


def build_permission_view(permission: str) -> dict[str, str]:
    tool = get_permission_tool(permission)
    category = get_permission_category_from_tool(tool)
    description = describe_permission(permission)

    return {
        "permission": permission,
        "tool": tool,
        "tool_label": format_permission_tool_label(tool),
        "category": category,
        "category_label": get_permission_category_label(category),
        "title": description["title"],
        "description": description["description"],
    }
