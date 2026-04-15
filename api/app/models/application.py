import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.environment import Environment


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chart_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    chart_repo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    owner_email: Mapped[str] = mapped_column(String(256), nullable=False)
    default_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="rolling")
    canary_steps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    app_metadata: Mapped[dict | None] = mapped_column("app_metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    team: Mapped["Team"] = relationship("Team", back_populates="applications")
    deployments: Mapped[list["ApplicationDeployment"]] = relationship(
        "ApplicationDeployment", back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationDeployment(Base):
    __tablename__ = "application_deployments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    argocd_app_name: Mapped[str] = mapped_column(String(256), nullable=False)
    image_tag: Mapped[str | None] = mapped_column(String(256), nullable=True)
    chart_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    health_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="rolling")
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    deployed_by: Mapped[str] = mapped_column(String(256), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_status: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    application: Mapped["Application"] = relationship("Application", back_populates="deployments")
    environment: Mapped["Environment"] = relationship(
        "Environment", back_populates="application_deployments"
    )
    events: Mapped[list["ApplicationDeploymentEvent"]] = relationship(
        "ApplicationDeploymentEvent",
        back_populates="deployment",
        cascade="all, delete-orphan",
    )


class ApplicationDeploymentEvent(Base):
    __tablename__ = "application_deployment_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application_deployments.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    to_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    deployment: Mapped["ApplicationDeployment"] = relationship(
        "ApplicationDeployment", back_populates="events"
    )
