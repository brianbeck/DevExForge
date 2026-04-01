import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CatalogTemplate(Base):
    __tablename__ = "catalog_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chart_repo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chart_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chart_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    values_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
