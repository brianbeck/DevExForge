"""Tiered policy floor enforcement.

Platform enforces minimum security standards per tier. Teams can make policies
stricter but never weaker than the floor.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyFloor:
    """Minimum policy requirements for a tier."""
    require_non_root: bool
    require_read_only_root: bool
    max_critical_cves: int
    max_high_cves: int
    require_resource_limits: bool


# Platform-enforced minimums per tier
TIER_FLOORS: dict[str, PolicyFloor] = {
    "dev": PolicyFloor(
        require_non_root=False,
        require_read_only_root=False,
        max_critical_cves=5,
        max_high_cves=20,
        require_resource_limits=False,
    ),
    "staging": PolicyFloor(
        require_non_root=True,
        require_read_only_root=False,
        max_critical_cves=0,
        max_high_cves=10,
        require_resource_limits=True,
    ),
    "production": PolicyFloor(
        require_non_root=True,
        require_read_only_root=True,
        max_critical_cves=0,
        max_high_cves=0,
        require_resource_limits=True,
    ),
}


def get_floor(tier: str) -> PolicyFloor:
    """Get the policy floor for a tier."""
    floor = TIER_FLOORS.get(tier)
    if floor is None:
        raise ValueError(f"Unknown tier: {tier}")
    return floor


def validate_policies_against_floor(tier: str, policies: dict | None) -> list[str]:
    """Validate that requested policies meet or exceed the tier floor.

    Returns a list of violation messages. Empty list means valid.
    """
    if policies is None:
        return []

    floor = get_floor(tier)
    violations = []

    # Boolean floors: if floor requires True, requested cannot be False
    if floor.require_non_root and not policies.get("requireNonRoot", True):
        violations.append(
            f"Tier '{tier}' requires requireNonRoot=true (platform minimum)"
        )
    if floor.require_read_only_root and not policies.get("requireReadOnlyRoot", False):
        violations.append(
            f"Tier '{tier}' requires requireReadOnlyRoot=true (platform minimum)"
        )
    if floor.require_resource_limits and not policies.get("requireResourceLimits", True):
        violations.append(
            f"Tier '{tier}' requires requireResourceLimits=true (platform minimum)"
        )

    # Integer floors: requested value cannot exceed (be more permissive than) the floor
    requested_critical = policies.get("maxCriticalCVEs", 0)
    if requested_critical > floor.max_critical_cves:
        violations.append(
            f"Tier '{tier}' allows at most maxCriticalCVEs={floor.max_critical_cves}, "
            f"requested {requested_critical}"
        )

    requested_high = policies.get("maxHighCVEs", 5)
    if requested_high > floor.max_high_cves:
        violations.append(
            f"Tier '{tier}' allows at most maxHighCVEs={floor.max_high_cves}, "
            f"requested {requested_high}"
        )

    return violations


def apply_floor_defaults(tier: str, policies: dict | None) -> dict:
    """Merge requested policies with tier floor, taking the stricter value.

    If no policies provided, returns the floor as defaults.
    """
    floor = get_floor(tier)

    if policies is None:
        return {
            "requireNonRoot": floor.require_non_root,
            "requireReadOnlyRoot": floor.require_read_only_root,
            "maxCriticalCVEs": floor.max_critical_cves,
            "maxHighCVEs": floor.max_high_cves,
            "requireResourceLimits": floor.require_resource_limits,
        }

    return {
        "requireNonRoot": floor.require_non_root or policies.get("requireNonRoot", False),
        "requireReadOnlyRoot": floor.require_read_only_root or policies.get("requireReadOnlyRoot", False),
        "maxCriticalCVEs": min(floor.max_critical_cves, policies.get("maxCriticalCVEs", floor.max_critical_cves)),
        "maxHighCVEs": min(floor.max_high_cves, policies.get("maxHighCVEs", floor.max_high_cves)),
        "requireResourceLimits": floor.require_resource_limits or policies.get("requireResourceLimits", False),
    }
