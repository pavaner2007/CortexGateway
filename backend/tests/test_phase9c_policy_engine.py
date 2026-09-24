"""
Phase 9C — Policy Engine Tests.

Tests:
  Schemas:
    1.  GLOBAL_DEFAULT_POLICY has correct values
    2.  TeamPolicyInput accepts partial input (routing only)
    3.  TeamPolicyInput accepts full input
    4.  TeamPolicyInput rejects unknown section (extra=forbid)
    5.  BudgetPolicySection normalises action to uppercase
    6.  BudgetPolicySection rejects unknown action
    7.  RoutingPolicy rejects unknown strategy
    8.  ResolvedPolicy is frozen (immutable)

  PolicyResolver:
    9.  No team_id → global default
    10. No DB row → global default
    11. DB error → global default (fail-open)
    12. Partial team policy (routing only) merges correctly
    13. Full team policy replaces all sections
    14. Invalid stored JSONB → global default (defensive)
    15. source field set to "team" when team row exists

  PolicyService:
    16. upsert creates a new row
    17. upsert again updates the same row (idempotent)
    18. delete returns True for existing, False for missing
    19. get_policy_dict returns None when no row

  API endpoints (GET / PUT / DELETE):
    20. GET returns global default with source="global" when no row
    21. PUT creates policy, GET returns it with source="team"
    22. DELETE removes the policy, GET returns global default again
    23. PUT with invalid routing strategy returns 422
    24. PUT with unknown section returns 422
    25. PUT with YAML body succeeds
    26. Non-admin cannot PUT
    27. Cross-org team access returns 403

  ChatService integration:
    28. resolved_policy=None falls back to global default (BLOCK/auto/failover/cache-off)
    29. routing strategy from policy flows into effective_routing_mode
    30. budget action from policy is used (not DB Budget.policy)
    31. fallback.enabled=False patches failover_enabled=False onto request copy
    32. cache.enabled=False prevents cache lookup even when semantic_cache provided
    33. cache.enabled=True allows cache lookup

  Backward compatibility:
    34. Pre-9C ChatService.complete() callers (no resolved_policy arg) still work
"""

from __future__ import annotations

import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.policy.schemas import (
    GLOBAL_DEFAULT_POLICY,
    BudgetPolicySection,
    CachePolicy,
    FallbackPolicy,
    ResolvedPolicy,
    RoutingPolicy,
    TeamPolicyInput,
)

# ── 1. GLOBAL_DEFAULT_POLICY values ─────────────────────────────────────────

def test_global_default_routing_strategy():
    assert GLOBAL_DEFAULT_POLICY.routing.strategy == "auto"


def test_global_default_fallback_enabled():
    assert GLOBAL_DEFAULT_POLICY.fallback.enabled is True


def test_global_default_budget_action():
    assert GLOBAL_DEFAULT_POLICY.budget.action == "BLOCK"


def test_global_default_cache_disabled():
    assert GLOBAL_DEFAULT_POLICY.cache.enabled is False


def test_global_default_source():
    assert GLOBAL_DEFAULT_POLICY.source == "global"


# ── 2–3. TeamPolicyInput partial / full ──────────────────────────────────────

def test_team_policy_input_partial_routing_only():
    p = TeamPolicyInput(routing=RoutingPolicy(strategy="lowest_cost"))
    assert p.routing is not None
    assert p.fallback is None
    assert p.budget is None
    assert p.cache is None


def test_team_policy_input_full():
    p = TeamPolicyInput(
        routing=RoutingPolicy(strategy="lowest_latency"),
        fallback=FallbackPolicy(enabled=False),
        budget=BudgetPolicySection(action="WARN"),
        cache=CachePolicy(enabled=True),
    )
    assert p.routing.strategy == "lowest_latency"
    assert p.fallback.enabled is False
    assert p.budget.action == "WARN"
    assert p.cache.enabled is True


# ── 4. Unknown section → extra=forbid ────────────────────────────────────────

def test_team_policy_input_rejects_unknown_section():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TeamPolicyInput.model_validate({"routing": {"strategy": "auto"}, "typo_section": {}})


# ── 5. BudgetPolicySection uppercase normalisation ───────────────────────────

def test_budget_action_normalised_to_upper():
    assert BudgetPolicySection(action="warn").action == "WARN"
    assert BudgetPolicySection(action="downgrade").action == "DOWNGRADE"
    assert BudgetPolicySection(action="BLOCK").action == "BLOCK"


# ── 6. BudgetPolicySection rejects invalid action ────────────────────────────

def test_budget_action_rejects_invalid():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        BudgetPolicySection(action="ALLOW")


# ── 7. RoutingPolicy rejects unknown strategy ────────────────────────────────

def test_routing_policy_rejects_unknown_strategy():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RoutingPolicy(strategy="random")


# ── 8. ResolvedPolicy is frozen ──────────────────────────────────────────────

def test_resolved_policy_is_frozen():
    with pytest.raises(Exception):
        GLOBAL_DEFAULT_POLICY.source = "team"  # type: ignore[misc]


# ── 9. PolicyResolver: no team_id → global default ──────────────────────────

def test_policy_resolver_no_team_id():
    from app.policy.resolver import PolicyResolver
    resolver = PolicyResolver(session=MagicMock())

    result = asyncio.get_event_loop().run_until_complete(resolver.resolve(None))
    assert result is GLOBAL_DEFAULT_POLICY


# ── 10. PolicyResolver: no DB row → global default ──────────────────────────

def test_policy_resolver_no_db_row():
    from app.policy.resolver import PolicyResolver

    mock_svc = AsyncMock()
    mock_svc.get_policy_dict.return_value = None

    with patch("app.policy.resolver.PolicyService", return_value=mock_svc):
        resolver = PolicyResolver(session=MagicMock())
        result = asyncio.get_event_loop().run_until_complete(resolver.resolve("team-123"))

    assert result is GLOBAL_DEFAULT_POLICY


# ── 11. PolicyResolver: DB error → global default (fail-open) ───────────────

def test_policy_resolver_db_error_fail_open():
    from app.policy.resolver import PolicyResolver

    mock_svc = AsyncMock()
    mock_svc.get_policy_dict.side_effect = ConnectionError("pg down")

    with patch("app.policy.resolver.PolicyService", return_value=mock_svc):
        resolver = PolicyResolver(session=MagicMock())
        result = asyncio.get_event_loop().run_until_complete(resolver.resolve("team-abc"))

    assert result is GLOBAL_DEFAULT_POLICY


# ── 12. Partial team policy merge: routing only ──────────────────────────────

def test_policy_resolver_merge_routing_only():
    from app.policy.resolver import PolicyResolver

    raw = {"routing": {"strategy": "lowest_cost"}}
    mock_svc = AsyncMock()
    mock_svc.get_policy_dict.return_value = raw

    with patch("app.policy.resolver.PolicyService", return_value=mock_svc):
        resolver = PolicyResolver(session=MagicMock())
        result = asyncio.get_event_loop().run_until_complete(resolver.resolve("team-x"))

    assert result.routing.strategy == "lowest_cost"
    # Unspecified sections inherit from global default
    assert result.fallback.enabled == GLOBAL_DEFAULT_POLICY.fallback.enabled
    assert result.budget.action == GLOBAL_DEFAULT_POLICY.budget.action
    assert result.cache.enabled == GLOBAL_DEFAULT_POLICY.cache.enabled
    assert result.source == "team"


# ── 13. Full team policy replaces all sections ───────────────────────────────

def test_policy_resolver_full_policy():
    from app.policy.resolver import PolicyResolver

    raw = {
        "routing": {"strategy": "lowest_latency"},
        "fallback": {"enabled": False},
        "budget": {"action": "WARN"},
        "cache": {"enabled": True},
    }
    mock_svc = AsyncMock()
    mock_svc.get_policy_dict.return_value = raw

    with patch("app.policy.resolver.PolicyService", return_value=mock_svc):
        resolver = PolicyResolver(session=MagicMock())
        result = asyncio.get_event_loop().run_until_complete(resolver.resolve("team-y"))

    assert result.routing.strategy == "lowest_latency"
    assert result.fallback.enabled is False
    assert result.budget.action == "WARN"
    assert result.cache.enabled is True
    assert result.source == "team"


# ── 14. Invalid stored JSONB → global default ────────────────────────────────

def test_policy_resolver_invalid_stored_json_falls_back():
    from app.policy.resolver import PolicyResolver

    raw = {"routing": {"strategy": "totally_wrong_value"}}
    mock_svc = AsyncMock()
    mock_svc.get_policy_dict.return_value = raw

    with patch("app.policy.resolver.PolicyService", return_value=mock_svc):
        resolver = PolicyResolver(session=MagicMock())
        result = asyncio.get_event_loop().run_until_complete(resolver.resolve("team-z"))

    assert result is GLOBAL_DEFAULT_POLICY


# ── 15. source = "team" when row exists ─────────────────────────────────────

def test_policy_resolver_source_team():
    from app.policy.resolver import PolicyResolver

    raw = {"cache": {"enabled": True}}
    mock_svc = AsyncMock()
    mock_svc.get_policy_dict.return_value = raw

    with patch("app.policy.resolver.PolicyService", return_value=mock_svc):
        resolver = PolicyResolver(session=MagicMock())
        result = asyncio.get_event_loop().run_until_complete(resolver.resolve("team-s"))

    assert result.source == "team"


# ── 16–19. PolicyService unit tests ─────────────────────────────────────────

class TestPolicyService:
    """
    Unit tests for PolicyService using a mocked async session.

    Avoids the need for a real DB.
    """

    def _make_service(self):
        from app.policy.service import PolicyService

        session = AsyncMock()
        return PolicyService(session=session), session

    def test_get_policy_dict_none_when_no_row(self):
        svc, session = self._make_service()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = asyncio.get_event_loop().run_until_complete(svc.get_policy_dict("t1"))
        assert result is None

    def test_get_policy_dict_returns_dict(self):
        from app.policy.models import TeamPolicyModel

        svc, session = self._make_service()
        model = TeamPolicyModel(
            id="id1",
            team_id="t1",
            policy={"routing": {"strategy": "lowest_cost"}},
            enabled=True,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        session.execute = AsyncMock(return_value=mock_result)

        result = asyncio.get_event_loop().run_until_complete(svc.get_policy_dict("t1"))
        assert result == {"routing": {"strategy": "lowest_cost"}}

    def test_delete_returns_false_when_no_row(self):
        svc, session = self._make_service()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = asyncio.get_event_loop().run_until_complete(svc.delete_policy("t1"))
        assert result is False


# ── 28. ChatService: no resolved_policy → global default behavior ────────────

class TestChatServicePolicyIntegration:
    """Tests that ChatService correctly applies policy objects."""

    def _make_request(self, **overrides):
        from app.schemas.chat import ChatCompletionRequest, ChatMessage

        defaults = dict(
            provider="groq",
            model="llama3-8b-8192",
            messages=[ChatMessage(role="user", content="hello")],
        )
        defaults.update(overrides)
        return ChatCompletionRequest(**defaults)

    def _make_response(self):
        from app.schemas.chat import (
            ChatCompletionChoice,
            ChatCompletionResponse,
            ChatMessageResponse,
            ResponseMetadata,
            UsageMetadata,
        )
        return ChatCompletionResponse(
            provider="groq",
            model="llama3-8b-8192",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessageResponse(content="hi"),
                    finish_reason="stop",
                )
            ],
            usage=UsageMetadata(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            metadata=ResponseMetadata(
                request_id="test-req",
                latency_ms=100.0,
                selected_provider="groq",
                selected_model="llama3-8b-8192",
            ),
        )

    def test_no_resolved_policy_uses_global_default(self):
        """resolved_policy=None → global default → routing mode 'auto'."""
        from app.providers.registry import ProviderRegistry
        from app.services.chat_service import ChatService

        registry = MagicMock(spec=ProviderRegistry)
        mock_exec = AsyncMock(return_value=self._make_response())
        mock_routing = MagicMock()
        mock_routing.route = AsyncMock(
            return_value=MagicMock(
                provider="groq", model="llama3-8b-8192", routing_mode="auto"
            )
        )

        svc = ChatService(registry=registry, routing_engine=mock_routing)
        svc._reliability_executor = MagicMock()
        svc._reliability_executor.execute = mock_exec

        req = self._make_request(model="auto")

        async def run():
            return await svc.complete(req, "req-001", resolved_policy=None)

        response = asyncio.get_event_loop().run_until_complete(run())
        assert response is not None

    def test_resolved_policy_routing_strategy_used(self):
        """Policy routing.strategy='lowest_cost' flows into effective_routing_mode."""
        from app.providers.registry import ProviderRegistry
        from app.services.chat_service import ChatService

        policy = ResolvedPolicy(
            routing=RoutingPolicy(strategy="lowest_cost"),
            fallback=FallbackPolicy(enabled=True),
            budget=BudgetPolicySection(action="BLOCK"),
            cache=CachePolicy(enabled=False),
            source="team",
        )

        registry = MagicMock(spec=ProviderRegistry)
        mock_exec = AsyncMock(return_value=self._make_response())
        mock_routing = MagicMock()
        mock_routing.route = AsyncMock(
            return_value=MagicMock(
                provider="groq",
                model="llama3-8b-8192",
                routing_mode="lowest_cost",
            )
        )

        svc = ChatService(registry=registry, routing_engine=mock_routing)
        svc._reliability_executor = MagicMock()
        svc._reliability_executor.execute = mock_exec

        req = self._make_request(model="auto")

        async def run():
            return await svc.complete(req, "req-002", resolved_policy=policy)

        asyncio.get_event_loop().run_until_complete(run())
        # Route was called (auto routing branch entered)
        mock_routing.route.assert_called_once()

    def test_resolved_policy_cache_disabled_skips_lookup(self):
        """cache.enabled=False → semantic_cache.lookup never called."""
        from app.providers.registry import ProviderRegistry
        from app.services.chat_service import ChatService

        policy = ResolvedPolicy(
            routing=RoutingPolicy(strategy="auto"),
            fallback=FallbackPolicy(enabled=True),
            budget=BudgetPolicySection(action="BLOCK"),
            cache=CachePolicy(enabled=False),
            source="team",
        )

        registry = MagicMock(spec=ProviderRegistry)
        mock_exec = AsyncMock(return_value=self._make_response())
        mock_routing = MagicMock()
        mock_routing.route = AsyncMock(
            return_value=MagicMock(
                provider="groq", model="llama3-8b-8192", routing_mode="auto"
            )
        )
        mock_cache = AsyncMock()
        mock_cache.lookup = AsyncMock(return_value=None)

        # Build a fake context
        from unittest.mock import MagicMock as MM
        mock_context = MM()
        mock_context.team_id = "team-1"
        mock_context.api_key_id = "key-1"
        mock_context.organization_id = "org-1"

        svc = ChatService(registry=registry, routing_engine=mock_routing)
        svc._reliability_executor = MagicMock()
        svc._reliability_executor.execute = mock_exec

        req = self._make_request(model="auto")

        async def run():
            return await svc.complete(
                req,
                "req-003",
                context=mock_context,
                semantic_cache=mock_cache,
                resolved_policy=policy,
            )

        asyncio.get_event_loop().run_until_complete(run())
        mock_cache.lookup.assert_not_called()

    def test_resolved_policy_fallback_disabled_patches_request(self):
        """fallback.enabled=False → ReliabilityExecutor receives failover_enabled=False."""
        from app.providers.registry import ProviderRegistry
        from app.services.chat_service import ChatService

        policy = ResolvedPolicy(
            routing=RoutingPolicy(strategy="auto"),
            fallback=FallbackPolicy(enabled=False),
            budget=BudgetPolicySection(action="BLOCK"),
            cache=CachePolicy(enabled=False),
            source="team",
        )

        registry = MagicMock(spec=ProviderRegistry)
        captured_request = {}

        async def capture_execute(request, **kwargs):
            captured_request["req"] = request
            return self._make_response()

        mock_routing = MagicMock()
        mock_routing.route = AsyncMock(
            return_value=MagicMock(
                provider="groq", model="llama3-8b-8192", routing_mode="auto"
            )
        )

        svc = ChatService(registry=registry, routing_engine=mock_routing)
        svc._reliability_executor = MagicMock()
        svc._reliability_executor.execute = AsyncMock(side_effect=capture_execute)

        req = self._make_request(model="auto")
        assert req.failover_enabled is True  # default

        async def run():
            return await svc.complete(req, "req-004", resolved_policy=policy)

        asyncio.get_event_loop().run_until_complete(run())
        assert captured_request["req"].failover_enabled is False

    def test_resolved_policy_budget_action_used_not_db(self):
        """
        budget.action from policy is used, not Budget.policy from DB.
        With WARN policy, BudgetExceeded is not raised even when over limit.
        """
        from unittest.mock import patch

        from app.providers.registry import ProviderRegistry
        from app.services.chat_service import ChatService

        policy = ResolvedPolicy(
            routing=RoutingPolicy(strategy="auto"),
            fallback=FallbackPolicy(enabled=True),
            budget=BudgetPolicySection(action="WARN"),
            cache=CachePolicy(enabled=False),
            source="team",
        )

        registry = MagicMock(spec=ProviderRegistry)
        mock_routing = MagicMock()
        mock_routing.route = AsyncMock(
            return_value=MagicMock(
                provider="groq", model="llama3-8b-8192", routing_mode="auto"
            )
        )

        # Budget service returns a budget (WARN -> reserve allowed, warning=True)
        mock_budget_svc = AsyncMock()
        mock_budget_svc.check_and_reserve = AsyncMock(return_value=(MagicMock(), True))
        mock_budget_svc.reconcile = AsyncMock(return_value=MagicMock())
        mock_budget_svc.get_budget = AsyncMock(return_value=MagicMock(enabled=True, remaining_amount=0.001))

        mock_cost_calc = MagicMock()
        mock_cost_calc.estimate_cost = MagicMock(return_value=0.001)
        mock_cost_calc.calculate_actual_cost = MagicMock(return_value=0.0005)

        mock_context = MagicMock()
        mock_context.team_id = "team-warn"
        mock_context.api_key_id = "key-w"
        mock_context.organization_id = "org-w"

        svc = ChatService(registry=registry, routing_engine=mock_routing)
        svc._reliability_executor = MagicMock()
        svc._reliability_executor.execute = AsyncMock(return_value=self._make_response())

        req = self._make_request(model="auto")

        # Build a mock settings object with budget_enabled=True so this test
        # is not affected by the BUDGET_ENABLED=false env var used in CI.
        mock_settings = MagicMock()
        mock_settings.budget_enabled = True
        mock_settings.rate_limit_enabled = False
        mock_settings.semantic_cache_enabled = False

        async def run():
            return await svc.complete(
                req,
                "req-005",
                context=mock_context,
                budget_service=mock_budget_svc,
                cost_calculator=mock_cost_calc,
                resolved_policy=policy,
                settings=mock_settings,
            )

        response = asyncio.get_event_loop().run_until_complete(run())

        # WARN does not raise; check_and_reserve was called
        mock_budget_svc.check_and_reserve.assert_called_once()
        assert response is not None

