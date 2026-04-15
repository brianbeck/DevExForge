import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.environment import Environment
    from app.models.application import Application, ApplicationDeployment


class PromotionGate(Base):
    __tablename__ = "promotion_gates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    enforcement: Mapped[str] = mapped_column(String(16), nullable=False, default="blocking")
    created_by: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class PromotionRequest(Base):
    __tablename__ = "promotion_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application_deployments.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environments.id"), nullable=False
    )
    source_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(256), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_gates")
    image_tag: Mapped[str | None] = mapped_column(String(256), nullable=True)
    chart_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="rolling")
    canary_steps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    force_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    forced_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    approver_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_revision: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped["Application"] = relationship(
        "Application", back_populates="promotion_requests"
    )
    from_deployment: Mapped["ApplicationDeployment | None"] = relationship(
        "ApplicationDeployment", foreign_keys=[from_deployment_id]
    )
    to_environment: Mapped["Environment"] = relationship(
        "Environment", foreign_keys=[to_environment_id]
    )
    gate_results: Mapped[list["PromotionGateResult"]] = relationship(
        "PromotionGateResult",
        back_populates="promotion_request",
        cascade="all, delete-orphan",
    )


class PromotionGateResult(Base):
    __tablename__ = "promotion_gate_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    promotion_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("promotion_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("promotion_gates.id", ondelete="SET NULL"),
        nullable=True,
    )
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    promotion_request: Mapped["PromotionRequest"] = relationship(
        "PromotionRequest", back_populates="gate_results"
    )
    gate: Mapped["PromotionGate | None"] = relationship(
        "PromotionGate", foreign_keys=[gate_id]
    )
