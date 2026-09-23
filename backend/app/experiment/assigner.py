"""
Cortex Gateway — Experiment Assigner (Phase 9D).

Deterministically assigns an experiment arm to a request using SHA-256 hashing.

Algorithm:
  hash_input = f"{team_id}:{experiment_id}:{experiment_version}:{request_id}"
  digest     = SHA-256(hash_input.encode("utf-8"))
  bucket     = int.from_bytes(digest[:4], "big") % 10_000   # 0–9999

  Bucket-to-arm mapping:
    Arms are iterated in declaration order.
    Each arm owns (weight * 100) consecutive buckets.
    Example (50/50):
      arm_a: buckets 0–4999
      arm_b: buckets 5000–9999
    Example (95/5):
      stable: buckets 0–9499
      canary: buckets 9500–9999

Properties:
  - Deterministic: same (team_id, experiment_id, version, request_id) → same arm.
  - Version-aware: changing experiment.version changes hash → different distribution.
  - No shared state: no rolling counters, no random.random().
  - Integer arithmetic only: no floating-point rounding errors.
  - Bucket size 10_000 gives 0.01% granularity per weight unit.

Usage:
  assignment = ExperimentAssigner.assign(
      team_id=...,
      request_id=...,
      experiment=resolved_policy.experiment,
  )
  if assignment is not None:
      target_provider = assignment.provider
      target_model    = assignment.model
"""

from __future__ import annotations

import hashlib

from app.core.logging import logger
from app.experiment.schemas import ExperimentAssignment
from app.policy.schemas import ExperimentConfig

# Bucket space: 10_000 — each weight % = 100 buckets.
# Gives 0.01% resolution, well within integer arithmetic.
_BUCKET_SIZE = 10_000


class ExperimentAssigner:
    """Stateless traffic assigner for Phase 9D experiments."""

    @staticmethod
    def assign(
        *,
        team_id: str,
        request_id: str,
        experiment: ExperimentConfig | None,
    ) -> ExperimentAssignment | None:
        """
        Assign a request to an experiment arm.

        Returns:
          ExperimentAssignment if the experiment is active and enabled.
          None if:
            - experiment is None (no experiment configured)
            - experiment.enabled is False
            - (safety) no arms defined

        Never raises. Any internal error is logged and returns None (fail-open).
        """
        if experiment is None:
            return None

        if not experiment.enabled:
            logger.debug(
                "Experiment disabled — skipping assignment",
                experiment_id=experiment.id,
            )
            return None

        if not experiment.arms:
            # Should not happen after schema validation, but defensive.
            logger.warning(
                "Experiment has no arms — skipping assignment",
                experiment_id=experiment.id,
            )
            return None

        try:
            return ExperimentAssigner._select_arm(
                team_id=team_id,
                request_id=request_id,
                experiment=experiment,
            )
        except Exception as exc:
            logger.error(
                "ExperimentAssigner: unexpected error — skipping assignment (fail-open)",
                experiment_id=experiment.id,
                error=str(exc),
            )
            return None

    @staticmethod
    def _select_arm(
        *,
        team_id: str,
        request_id: str,
        experiment: ExperimentConfig,
    ) -> ExperimentAssignment:
        """
        Core deterministic arm selection.

        Hash input: "<team_id>:<experiment_id>:<experiment_version>:<request_id>"
        Hash algo:  SHA-256
        Bucket:     first 4 bytes of digest → big-endian uint32 → mod 10_000

        Cumulative weight mapping (integer arithmetic, declaration order):
          arm_a weight=50 → cumulative threshold =  5000
          arm_b weight=50 → cumulative threshold = 10000
          bucket 0–4999   → arm_a
          bucket 5000–9999 → arm_b
        """
        hash_input = (
            f"{team_id}:{experiment.id}:{experiment.version}:{request_id}"
        )
        digest = hashlib.sha256(hash_input.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % _BUCKET_SIZE

        # Build cumulative thresholds (each weight unit = 100 buckets)
        cumulative = 0
        selected_arm = experiment.arms[-1]  # fallback: last arm (should never fire)
        for arm in experiment.arms:
            cumulative += arm.weight * (_BUCKET_SIZE // 100)
            if bucket < cumulative:
                selected_arm = arm
                break

        logger.debug(
            "Experiment arm assigned",
            experiment_id=experiment.id,
            experiment_version=experiment.version,
            experiment_type=experiment.type,
            arm_name=selected_arm.name,
            provider=selected_arm.provider,
            model=selected_arm.model,
            bucket=bucket,
            team_id=team_id,
            request_id=request_id,
        )

        return ExperimentAssignment(
            experiment_id=experiment.id,
            experiment_version=experiment.version,
            arm_name=selected_arm.name,
            provider=selected_arm.provider,
            model=selected_arm.model,
        )
