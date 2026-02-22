from __future__ import annotations

from datetime import datetime, date, timezone
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Table,
    Column,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def utcnow() -> datetime:
    """Get the current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# --- RBAC association tables ---
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id"), primary_key=True),
)


# --- Core models ---
class User(Base):
    """
    Application user model.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)

    roles: Mapped[list["Role"]] = relationship("Role", secondary=user_roles)


class Role(Base):
    """
    Role model representing a user role.
    """
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    permissions: Mapped[list["Permission"]] = relationship("Permission", secondary=role_permissions)


class Permission(Base):
    """
    Permission model representing a specific permission.
    """
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class PermissionGrant(Base):
    """
    User-specific permission grant (outside role membership).
    """
    __tablename__ = "permission_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    permission_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    granted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Delegation(Base):
    """
    Delegation from grantor(target owner) -> grantee(actor), scoped by permission_name.
    """
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(primary_key=True)
    grantor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    grantee_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    permission_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PermissionRequest(Base):
    """
    Request for either a direct user permission grant or a delegation.
    """
    __tablename__ = "permission_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    request_kind: Mapped[str] = mapped_column(String, nullable=False)  # permission|delegation
    permission_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)  # pending|approved|rejected
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    """
    Durable per-user notifications for SSE delivery and historical viewing.
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Alarm(Base):
    """
    Server-scheduled alarm.
    """
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    fire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


# --- Domain models ---
class Note(Base):
    """
    Note model representing a user's note.
    """
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Task(Base):
    """
    Task model representing a user's task.
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    due_on: Mapped[date | None] = mapped_column(nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


# --- Agent tracing ---
class AgentRun(Base):
    """
    AgentRun model representing a single run of an agent.
    """
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    final_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialist_key: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="ok", nullable=False)  # ok|error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # IMPORTANT: explicitly point relationship at the FK column
    tools: Mapped[list["ToolAudit"]] = relationship(
        "ToolAudit",
        back_populates="run",
        foreign_keys=lambda: [ToolAudit.agent_run_id],
        # keep it simple; don't do delete-orphan with nullable FK
        cascade="save-update, merge",
    )
    conversation: Mapped["Conversation | None"] = relationship(
        "Conversation",
        back_populates="runs",
        foreign_keys=[conversation_id],
    )


class Conversation(Base):
    """
    Conversation model grouping multiple agent runs into one chat thread.
    """
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="default", index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)

    runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="conversation",
        foreign_keys=lambda: [AgentRun.conversation_id],
        cascade="save-update, merge",
    )


class ToolAudit(Base):
    """
    ToolAudit model representing a single tool invocation by an agent.
    """
    __tablename__ = "tool_audit"

    id: Mapped[int] = mapped_column(primary_key=True)

    # THIS is what fixes your error (SQLAlchemy must see this FK)
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id"),
        nullable=True,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    arguments: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    run: Mapped["AgentRun | None"] = relationship(
        "AgentRun",
        back_populates="tools",
        foreign_keys=[agent_run_id],
    )


class TokenUsageEvent(Base):
    """
    Persistent token usage event for LLM and speech transcription calls.
    """
    __tablename__ = "token_usage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True, index=True)

    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # llm|transcription
    provider: Mapped[str] = mapped_column(String, nullable=False, default="openai")
    model: Mapped[str | None] = mapped_column(String, nullable=True)

    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
