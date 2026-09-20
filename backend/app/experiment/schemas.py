"""
Cortex Gateway — Experiment Assignment Result (Phase 9D).

ExperimentAssignment is an immutable dataclass produced by ExperimentAssigner.assign().
It is created ONCE per request (after cache MISS, before budget) and stored for
the lifetime of the request.

Fields:
  experiment_id      — stable experiment identifier (from ExperimentConfig.id)
  experiment_version — version at the time of assignment (from ExperimentConfig.version)
  arm_name           — name of the selected arm (e.g. "canary", "arm_a")
  provider           — provider to route to (from the selected arm)
  model              — model to route to (from the selected arm)

Semantics:
  experiment_arm (arm_name) = arm ASSIGNED by the experiment.
  provider / model           = provider/model that actually serves the response
                               (may differ if Phase 4 failover occurs).

These must be stored separately in RequestLog:
  experiment_arm  = assigned arm name
  provider        = actual serving provider  (from response.metadata.selected_provider)
  model           = actual serving model     (from response.metadata.selected_model)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentAssignment:
    """Immutable result of experiment arm assignment for one request."""

    experiment_id: str
    experiment_version: int
    arm_name: str
    provider: str
    model: str
