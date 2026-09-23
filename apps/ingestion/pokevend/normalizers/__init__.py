"""Normalizers turn source payloads into canonical domain records."""

from pokevend.normalizers.machine_normalizer import (
    apply_verification,
    filter_by_radius,
    merge_machine,
    normalize_machines,
)
from pokevend.normalizers.observation_normalizer import (
    MachineMatcher,
    deduplicate,
    normalize_observations,
)

__all__ = [
    "MachineMatcher",
    "apply_verification",
    "deduplicate",
    "filter_by_radius",
    "merge_machine",
    "normalize_machines",
    "normalize_observations",
]
