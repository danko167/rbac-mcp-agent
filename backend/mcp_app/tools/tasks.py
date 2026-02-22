from __future__ import annotations

from sqlalchemy import select, update, delete

from app.db.db import SessionLocal
from app.db.models import Task
from app.security.authz import authorize
from app.services.notifications import create_notification
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call
from mcp_app.services.due_dates import resolve_due_on


def register(mcp):
    @mcp.tool()
    def tasks_list(
        auth: str,
        due_on: str | None = None,
        completed: bool | None = None,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        List tasks, optionally filtered by due date and completion status.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "tasks:list", target_user_id=target_user_id)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="tasks.list",
                args={"due_on": due_on, "completed": completed, "target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            stmt = select(Task).where(Task.owner_id == effective_target)
            if due_on:
                stmt = stmt.where(Task.due_on == resolve_due_on(due_on))
            if completed is not None:
                stmt = stmt.where(Task.completed == completed)

            tasks = db.scalars(stmt).all()
            return [
                {"id": t.id, "title": t.title, "due_on": t.due_on, "completed": t.completed}
                for t in tasks
            ]

    @mcp.tool()
    def tasks_create(
        auth: str,
        title: str,
        due_on: str | None = None,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Create a new task.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "tasks:create", target_user_id=target_user_id)

            task = Task(
                owner_id=effective_target,
                title=title,
                due_on=resolve_due_on(due_on),
                completed=False,
            )
            db.add(task)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="tasks.create",
                args={"title": title, "due_on": due_on, "target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            db.flush()

            if effective_target != identity.user_id:
                create_notification(
                    db,
                    user_id=effective_target,
                    event_type="resource.assigned",
                    payload={
                        "resource_type": "task",
                        "resource_id": task.id,
                        "actor_user_id": identity.user_id,
                    },
                    enqueue=False,
                )

            return {"id": task.id, "title": task.title}

    @mcp.tool()
    def tasks_update(
        auth: str,
        task_id: int,
        title: str | None = None,
        due_on: str | None = None,
        completed: bool | None = None,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Update a task by ID.
        """
        values: dict[str, object] = {}
        if title is not None:
            values["title"] = title
        if due_on is not None:
            values["due_on"] = resolve_due_on(due_on)
        if completed is not None:
            values["completed"] = completed
        if not values:
            raise ValueError("No fields provided to update")

        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "tasks:update", target_user_id=target_user_id)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="tasks.update",
                args={
                    "task_id": task_id,
                    "title": title,
                    "due_on": due_on,
                    "completed": completed,
                    "target_user_id": target_user_id,
                },
                agent_run_id=agent_run_id,
            )

            stmt = (
                update(Task)
                .where(Task.id == task_id, Task.owner_id == effective_target)
                .values(**values)
                .returning(Task.id, Task.title, Task.due_on, Task.completed)
            )
            row = db.execute(stmt).first()
            if not row:
                raise ValueError("Task not found")

            return {"id": row.id, "title": row.title, "due_on": row.due_on, "completed": row.completed}

    @mcp.tool()
    def tasks_complete(
        auth: str,
        task_id: int,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Mark a task as completed by ID.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "tasks:complete", target_user_id=target_user_id)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="tasks.complete",
                args={"task_id": task_id, "target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            stmt = (
                update(Task)
                .where(Task.id == task_id, Task.owner_id == effective_target)
                .values(completed=True)
                .returning(Task.id, Task.title, Task.completed)
            )
            row = db.execute(stmt).first()
            if not row:
                raise ValueError("Task not found")

            return {"id": row.id, "title": row.title, "completed": row.completed}

    @mcp.tool()
    def tasks_delete(
        auth: str,
        task_id: int,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Delete a task by ID.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "tasks:delete", target_user_id=target_user_id)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="tasks.delete",
                args={"task_id": task_id, "target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            stmt = delete(Task).where(Task.id == task_id, Task.owner_id == effective_target)
            res = db.execute(stmt)
            if res.rowcount == 0:
                raise ValueError("Task not found")

            return {"ok": True}
