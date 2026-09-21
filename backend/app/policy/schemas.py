"""
Cortex Gateway -- Policy Engine Schemas (Phase 9C + 9D + 9E).

Defines the declarative team policy structure and the global default policy.

Design:
  - TeamPolicy accepts partial input -- only the sections a team specifies are
    stored.  Unspecified sections fall back to the global default at resolution
    time.
  - ResolvedPolicy is always fully populated -- all sections present -- so
    downstream consumers never need to handle None.
  - Extra fields are forbidden on both models so that typos in section names
    (e.g. "routng") are rejected with a validation error rather than silently
    dropped.

Accepted values:
  routing.strategy       : manual | auto | lowest_cost | lowest_latency |
                           best_available | capability_based
  fallback.enabled       : bool
  budget.action          : BLOCK | WARN | DOWNGRADE  (normalised to upper-case)
  cache.enabled          : bool
  guardrails.*           : see GuardrailsPolicy

Phase 9D additions:
  experiment.enabled : bool
  experiment.id      : str
  experiment.version : int
  experiment.type    : ab_test | canary
  experiment.arms    : list of ExperimentArm (min 2, unique names, sum==100)

Phase 9E additions:
  guardrails.max_prompt_length   : int | null  (null = disabled)
  guardrails.pii_detection       : off | warn | block
  guardrails.injection_detection : off | warn | block
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class RoutingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Literal["manual","auto","lowest_cost","lowest_latency","best_available","capability_based"] = "auto"


class FallbackPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True


class BudgetPolicySection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["BLOCK", "WARN", "DOWNGRADE"] = "BLOCK"

    @field_validator("action", mode="before")
    @classmethod
    def normalise_action(cls, v: object) -> str:
        if isinstance(v, str):
            return v.strip().upper()
        raise ValueError(f"budget.action must be a string, got {type(v).__name__}")


class CachePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False


class GuardrailsPolicy(BaseModel):
    """
    Phase 9E guardrail configuration stored in the team policy.

    Defaults are deliberately permissive (all off / no limit) so that
    existing teams without explicit guardrail configuration are unaffected.

    Fields:
        max_prompt_length:    Maximum combined Unicode character count across
                              all messages.  None = no restriction.
                              Measurement is len(text), NOT token count.
        pii_detection:        off | warn | block
                              off   -> detector does not execute.
                              warn  -> log and continue.
                              block -> reject request (no rate-limit/budget cost).
        injection_detection:  off | warn | block  (same semantics as above).

    Limitations (must be disclosed to operators):
        - PII detection is pattern-based; it is not a comprehensive PII
          classifier and will produce false positives and false negatives.
        - Injection detection is heuristic-based; it is not a complete
          prompt-injection defense and must not be treated as a security
          boundary.
    """
    model_config = ConfigDict(extra="forbid")

    max_prompt_length: Optional[int] = None
    pii_detection: Literal["off", "warn", "block"] = "off"
    injection_detection: Literal["off", "warn", "block"] = "off"


class ExperimentArm(BaseModel):
    """Single traffic arm in an A/B or canary experiment."""
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str
    model: str
    weight: int

    @field_validator("weight")
    @classmethod
    def weight_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"arm weight must be > 0, got {v}")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("arm name must not be empty")
        return v.strip()

    @field_validator("provider")
    @classmethod
    def provider_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("arm provider must not be empty")
        return v.strip().lower()

    @field_validator("model")
    @classmethod
    def model_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("arm model must not be empty")
        return v.strip()


class ExperimentConfig(BaseModel):
    """
    Phase 9D experiment configuration stored in the team policy JSONB.

    Validation rules:
      - Minimum 2 arms.
      - Arm names must be unique.
      - Sum of arm weights must equal exactly 100.
      - type is "ab_test" or "canary" (same algorithm, different semantics).

    version:
      Included in SHA-256 hash input. Admin must increment when changing
      arms/weights/providers to distinguish old vs new configuration in logs.
    """
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    id: str
    version: int = 1
    type: Literal["ab_test", "canary"]
    arms: List[ExperimentArm]

    @field_validator("id")
    @classmethod
    def id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("experiment.id must not be empty")
        return v.strip()

    @field_validator("version")
    @classmethod
    def version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("experiment.version must be >= 1")
        return v

    @model_validator(mode="after")
    def validate_arms(self) -> "ExperimentConfig":
        arms = self.arms
        if len(arms) < 2:
            raise ValueError(f"experiment must have at least 2 arms, got {len(arms)}")
        names = [a.name for a in arms]
        if len(names) != len(set(names)):
            dupes = [n for n in names if names.count(n) > 1]
            raise ValueError(f"duplicate arm names in experiment: {sorted(set(dupes))}")
        total = sum(a.weight for a in arms)
        if total != 100:
            raise ValueError(
                f"sum of arm weights must equal 100, got {total} "
                f"({' + '.join(str(a.weight) for a in arms)})"
            )
        return self


class TeamPolicyInput(BaseModel):
    """
    Input schema for PUT /api/v1/teams/{team_id}/policy.
    All sections optional. Extra fields forbidden.
    Phase 9D: experiment section is optional.
    Phase 9E: guardrails section is optional.
    """
    model_config = ConfigDict(extra="forbid")

    routing: Optional[RoutingPolicy] = None
    fallback: Optional[FallbackPolicy] = None
    budget: Optional[BudgetPolicySection] = None
    cache: Optional[CachePolicy] = None
    experiment: Optional[ExperimentConfig] = None
    guardrails: Optional[GuardrailsPolicy] = None


class ResolvedPolicy(BaseModel):
    """
    Fully-merged immutable policy from PolicyResolver.
    Phase 9D: experiment=None means no active experiment.
    Phase 9E: guardrails defaults to all-off (backward compatible).
    """
    model_config = ConfigDict(frozen=True)

    routing: RoutingPolicy
    fallback: FallbackPolicy
    budget: BudgetPolicySection
    cache: CachePolicy
    source: Literal["global", "team"]
    experiment: Optional[ExperimentConfig] = None
    guardrails: GuardrailsPolicy = GuardrailsPolicy()


GLOBAL_DEFAULT_POLICY = ResolvedPolicy(
    routing=RoutingPolicy(strategy="auto"),
    fallback=FallbackPolicy(enabled=True),
    budget=BudgetPolicySection(action="BLOCK"),
    cache=CachePolicy(enabled=False),
    source="global",
    experiment=None,
    # Phase 9E: all guardrails off by default -- backward compatible.
    # Existing teams without guardrail config are completely unaffected.
    guardrails=GuardrailsPolicy(
        max_prompt_length=None,
        pii_detection="off",
        injection_detection="off",
    ),
)
