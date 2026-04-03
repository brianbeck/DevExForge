import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_quota: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    limit_range: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    network_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    policies: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    argocd_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cluster: Mapped[str | None] = mapped_column(String(64), nullable=True)
    namespace_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(64), nullable=False, default="Pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    team: Mapped["Team"] = relationship("Team", back_populates="environments")
