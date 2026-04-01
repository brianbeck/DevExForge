"""Unit tests for app.services.policy_service (no HTTP, no fixtures)."""

import pytest

from app.services.policy_service import (
    apply_floor_defaults,
    get_floor,
    validate_policies_against_floor,
)


# ---- get_floor ------------------------------------------------------------

def test_get_floor_dev():
    f = get_floor("dev")
    assert f.require_non_root is False
    assert f.max_critical_cves == 5
    assert f.max_high_cves == 20
    assert f.require_resource_limits is False


def test_get_floor_staging():
    f = get_floor("staging")
    assert f.require_non_root is True
    assert f.max_critical_cves == 0
    assert f.max_high_cves == 10
    assert f.require_resource_limits is True


def test_get_floor_production():
    f = get_floor("production")
    assert f.require_non_root is True
    assert f.require_read_only_root is True
    assert f.max_critical_cves == 0
    assert f.max_high_cves == 0
    assert f.require_resource_limits is True


def test_get_floor_unknown_tier():
    with pytest.raises(ValueError, match="Unknown tier"):
        get_floor("fantasy")


# ---- validate_policies_against_floor ---------------------------------------

def test_validate_policies_valid():
    """Dev tier with permissive but within-floor policies -> no violations."""
    policies = {
        "requireNonRoot": False,
        "requireReadOnlyRoot": False,
        "maxCriticalCVEs": 3,
        "maxHighCVEs": 10,
        "requireResourceLimits": False,
    }
    violations = validate_policies_against_floor("dev", policies)
    assert violations == []


def test_validate_policies_none_is_valid():
    """None policies always pass validation."""
    assert validate_policies_against_floor("production", None) == []


def test_validate_policies_too_permissive():
    """Production with maxCriticalCVEs=5 violates the floor (max is 0)."""
    policies = {
        "requireNonRoot": True,
        "requireReadOnlyRoot": True,
        "maxCriticalCVEs": 5,
        "maxHighCVEs": 0,
        "requireResourceLimits": True,
    }
    violations = validate_policies_against_floor("production", policies)
    assert len(violations) == 1
    assert "maxCriticalCVEs" in violations[0]


def test_validate_policies_multiple_violations():
    """Production with several weaker-than-floor values."""
    policies = {
        "requireNonRoot": False,
        "requireReadOnlyRoot": False,
        "maxCriticalCVEs": 2,
        "maxHighCVEs": 5,
        "requireResourceLimits": False,
    }
    violations = validate_policies_against_floor("production", policies)
    assert len(violations) == 5  # all five fields violate


# ---- apply_floor_defaults --------------------------------------------------

def test_apply_floor_defaults_none():
    """None policies -> returns floor defaults."""
    result = apply_floor_defaults("production", None)
    assert result["requireNonRoot"] is True
    assert result["requireReadOnlyRoot"] is True
    assert result["maxCriticalCVEs"] == 0
    assert result["maxHighCVEs"] == 0
    assert result["requireResourceLimits"] is True


def test_apply_floor_defaults_stricter():
    """Policies stricter than floor are preserved."""
    policies = {
        "requireNonRoot": True,
        "requireReadOnlyRoot": True,
        "maxCriticalCVEs": 0,
        "maxHighCVEs": 0,
        "requireResourceLimits": True,
    }
    result = apply_floor_defaults("dev", policies)
    # All values are stricter than dev floor -> kept as-is
    assert result["requireNonRoot"] is True
    assert result["requireReadOnlyRoot"] is True
    assert result["maxCriticalCVEs"] == 0
    assert result["maxHighCVEs"] == 0
    assert result["requireResourceLimits"] is True


def test_apply_floor_defaults_weaker_clamped():
    """Policies weaker than floor are clamped to the floor."""
    policies = {
        "requireNonRoot": False,
        "requireReadOnlyRoot": False,
        "maxCriticalCVEs": 99,
        "maxHighCVEs": 99,
        "requireResourceLimits": False,
    }
    result = apply_floor_defaults("staging", policies)
    floor = get_floor("staging")
    assert result["requireNonRoot"] is True  # clamped
    assert result["requireReadOnlyRoot"] is False  # staging floor is False
    assert result["maxCriticalCVEs"] == floor.max_critical_cves  # 0
    assert result["maxHighCVEs"] == floor.max_high_cves  # 10
    assert result["requireResourceLimits"] is True  # clamped
