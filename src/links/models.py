from sqlalchemy import Table, Column, Integer, String, MetaData, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from auth.db import Base

links = Table(
    "links",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("original_url", String, nullable=False),
    Column("short_code", String, unique=True, nullable=False),
    Column("owner_id", UUID(as_uuid=True), ForeignKey("user.id"), nullable=True),
    Column("click_count", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_used_at", DateTime(timezone=True), nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=True),
)