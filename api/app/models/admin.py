import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QuotaPreset(Base):
    __tablename__ = "quota_presets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    cpu_request: Mapped[str] = mapped_column(String(32), nullable=False, default="2")
    cpu_limit: Mapped[str] = mapped_column(String(32), nullable=False, default="4")
    memory_request: Mapped[str] = mapped_column(String(32), nullable=False, default="4Gi")
    memory_limit: Mapped[str] = mapped_column(String(32), nullable=False, default="8Gi")
    pods: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    services: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    pvcs: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class PolicyProfile(Base):
    __tablename__ = "policy_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    max_critical_cves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_high_cves: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    require_non_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_read_only_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_resource_limits: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
