"""
Cortex Gateway — SQLAlchemy Declarative Base.

All ORM models inherit from this single Base so that:
- Alembic can discover all tables via Base.metadata
- Table relationships can be expressed with foreign keys
- A single shared MetaData object governs the schema

Import Base here; never create multiple Base instances.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all Cortex Gateway ORM models."""
    pass
