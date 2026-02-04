import json
from sqlalchemy.orm import Session
from app.db.models import ToolAudit


def log_tool_call(
    db: Session,
    *,
    user_id: int,
    tool: str,
    args: dict,
    agent_run_id: int | None,
) -> None:
    """
    Log a tool call to the ToolAudit table.
    """
    db.add(
        ToolAudit(
            user_id=user_id,
            tool_name=tool,
            arguments=json.dumps(args),
            agent_run_id=agent_run_id,
        )
    )
    db.flush()
