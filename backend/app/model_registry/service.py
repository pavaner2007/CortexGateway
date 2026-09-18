"""
Cortex Gateway — Model Registry Service (Phase 9A).

Responsibilities:
  - CRUD operations for ModelRegistryEntry rows
  - Metadata lookup used by ModelMetadataCatalog (Phase 3 + Phase 6)
  - Bulk load for catalog refresh

Design notes:
  - All DB operations use the injected AsyncSession.
  - list_models() returns enabled-only by default (routing only uses enabled models).
  - get_all_for_catalog() returns all enabled entries for catalog reload.
  - Duplicate (provider, model_name) raises ModelAlreadyExistsError (→ 409).
  - Missing entry raises ModelNotFoundError (→ 404).
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.model_registry.exceptions import ModelAlreadyExistsError, ModelNotFoundError
from app.model_registry.models import ModelRegistryEntry
from app.model_registry.schemas import ModelRegistryCreate, ModelRegistryUpdate


class ModelRegistryService:
    """CRUD service for the model_registry table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_model(self, data: ModelRegistryCreate) -> ModelRegistryEntry:
        """
        Insert a new registry entry.

        Raises:
            ModelAlreadyExistsError: if (provider, model_name) already exists.
        """
        # Check for duplicate before insert (friendlier error than IntegrityError)
        existing = await self._get_by_provider_model(data.provider, data.model_name)
        if existing is not None:
            raise ModelAlreadyExistsError(data.provider, data.model_name)

        entry = ModelRegistryEntry(
            provider=data.provider,
            model_name=data.model_name,
            display_name=data.display_name,
            input_cost_per_1k=data.input_cost_per_1k,
            output_cost_per_1k=data.output_cost_per_1k,
            capabilities=data.capabilities,
            context_window=data.context_window,
            baseline_latency_ms=data.baseline_latency_ms,
            enabled=data.enabled,
        )
        self._session.add(entry)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            raise ModelAlreadyExistsError(data.provider, data.model_name)
        return entry

    # ── Read ──────────────────────────────────────────────────────────────────

    async def list_models(
        self,
        provider: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[ModelRegistryEntry]:
        """
        List model registry entries.

        Args:
            provider:     Filter by provider name (case-insensitive). None = all providers.
            enabled_only: If True (default), return only enabled=true entries.
        """
        stmt = select(ModelRegistryEntry)
        if enabled_only:
            stmt = stmt.where(ModelRegistryEntry.enabled.is_(True))
        if provider:
            stmt = stmt.where(ModelRegistryEntry.provider == provider.lower())
        stmt = stmt.order_by(
            ModelRegistryEntry.provider,
            ModelRegistryEntry.model_name,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_model(self, model_id: str) -> ModelRegistryEntry:
        """
        Retrieve a single entry by ID.

        Raises:
            ModelNotFoundError: if the entry does not exist.
        """
        result = await self._session.execute(
            select(ModelRegistryEntry).where(ModelRegistryEntry.id == model_id)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise ModelNotFoundError(model_id)
        return entry

    async def get_all_for_catalog(self) -> List[ModelRegistryEntry]:
        """
        Return all ENABLED entries for bulk catalog population.
        Called by ModelMetadataCatalog.load_from_db().
        """
        return await self.list_models(enabled_only=True)

    # ── Update ────────────────────────────────────────────────────────────────

    async def update_model(
        self, model_id: str, data: ModelRegistryUpdate
    ) -> ModelRegistryEntry:
        """
        Partially update a registry entry.

        Raises:
            ModelNotFoundError: if the entry does not exist.
        """
        entry = await self.get_model(model_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(entry, field, value)

        await self._session.flush()
        return entry

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_model(self, model_id: str) -> None:
        """
        Delete a registry entry permanently.

        Raises:
            ModelNotFoundError: if the entry does not exist.
        """
        entry = await self.get_model(model_id)
        await self._session.delete(entry)
        await self._session.flush()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get_by_provider_model(
        self, provider: str, model_name: str
    ) -> Optional[ModelRegistryEntry]:
        result = await self._session.execute(
            select(ModelRegistryEntry).where(
                ModelRegistryEntry.provider == provider,
                ModelRegistryEntry.model_name == model_name,
            )
        )
        return result.scalar_one_or_none()
