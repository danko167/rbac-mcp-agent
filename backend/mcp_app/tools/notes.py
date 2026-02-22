from __future__ import annotations

from sqlalchemy import select, update, delete

from app.db.db import SessionLocal
from app.db.models import Note
from app.security.authz import authorize
from app.services.notifications import create_notification
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call


def register(mcp):
    @mcp.tool()
    def notes_list(
        auth: str,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        List all notes for the authenticated user.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "notes:list", target_user_id=target_user_id)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="notes.list",
                args={"target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            notes = db.scalars(select(Note).where(Note.owner_id == effective_target)).all()
            return [{"id": n.id, "title": n.title, "content": n.content} for n in notes]

    @mcp.tool()
    def notes_create(
        title: str,
        content: str,
        auth: str,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Create a new note for the authenticated user.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "notes:create", target_user_id=target_user_id)

            note = Note(owner_id=effective_target, title=title, content=content)
            db.add(note)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="notes.create",
                args={"title": title, "target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            # ensure note.id exists before returning
            db.flush()
            if effective_target != identity.user_id:
                create_notification(
                    db,
                    user_id=effective_target,
                    event_type="resource.assigned",
                    payload={
                        "resource_type": "note",
                        "resource_id": note.id,
                        "actor_user_id": identity.user_id,
                    },
                    enqueue=False,
                )

            return {"id": note.id, "title": note.title}

    @mcp.tool()
    def notes_update(
        auth: str,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Update an existing note for the authenticated user.
        """
        values: dict[str, object] = {}
        if title is not None:
            values["title"] = title
        if content is not None:
            values["content"] = content
        if not values:
            raise ValueError("No fields provided to update")

        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "notes:update", target_user_id=target_user_id)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="notes.update",
                args={
                    "note_id": note_id,
                    "title": title,
                    "content": content,
                    "target_user_id": target_user_id,
                },
                agent_run_id=agent_run_id,
            )

            stmt = (
                update(Note)
                .where(Note.id == note_id, Note.owner_id == effective_target)
                .values(**values)
                .returning(Note.id, Note.title, Note.content)
            )
            row = db.execute(stmt).first()
            if not row:
                raise ValueError("Note not found")

            return {"id": row.id, "title": row.title, "content": row.content}

    @mcp.tool()
    def notes_delete(
        auth: str,
        note_id: int,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Delete a note for the authenticated user.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "notes:delete", target_user_id=target_user_id)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="notes.delete",
                args={"note_id": note_id, "target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            stmt = delete(Note).where(Note.id == note_id, Note.owner_id == effective_target)
            res = db.execute(stmt)
            if res.rowcount == 0:
                raise ValueError("Note not found")

            return {"ok": True}
