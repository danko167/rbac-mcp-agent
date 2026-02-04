from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.models import AgentRun


def create_agent_run(db: Session, *, user_id: int, prompt: str) -> int:
    """Create a new agent run record in the database."""
    run = AgentRun(user_id=user_id, prompt=prompt, status="ok", error=None)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run.id


def finalize_agent_run_ok(db: Session, *, run_id: int, output: str) -> None:
    """Finalize an agent run with a successful output."""
    run = db.get(AgentRun, run_id)
    if run is None:
        raise ValueError(f"AgentRun {run_id} not found")

    run.final_output = output
    run.status = "ok"
    run.error = None
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def finalize_agent_run_error(db: Session, *, run_id: int, error: str) -> None:
    """Finalize an agent run with an error status."""
    run = db.get(AgentRun, run_id)
    if run is None:
        raise ValueError(f"AgentRun {run_id} not found")

    run.status = "error"
    run.error = error
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
