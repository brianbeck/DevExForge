"""Unit tests for rollout_service manifest builders and CRD-check cache."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import rollout_service
from app.services.rollout_service import (
    DEFAULT_CANARY_STEPS,
    build_rollout_manifest,
    check_rollouts_available,
)

# Only the async CRD-check test needs asyncio; sync builder tests do not.


def _fake_app(
    name: str = "svc",
    repo_url: str = "https://github.com/acme/svc",
) -> SimpleNamespace:
    return SimpleNamespace(name=name, repo_url=repo_url)


def test_build_rollout_manifest_bluegreen_shape():
    manifest = build_rollout_manifest(
        _fake_app(),
        target_namespace="acme-production",
        image_tag="v1.2.3",
        strategy="bluegreen",
        active_service="svc-active",
        preview_service="svc-preview",
    )
    assert manifest["apiVersion"] == "argoproj.io/v1alpha1"
    assert manifest["kind"] == "Rollout"
    assert manifest["metadata"]["namespace"] == "acme-production"
    strategy = manifest["spec"]["strategy"]
    assert "blueGreen" in strategy
    bg = strategy["blueGreen"]
    assert bg["activeService"] == "svc-active"
    assert bg["previewService"] == "svc-preview"
    assert bg["autoPromotionEnabled"] is False
    # canary shouldn't be present
    assert "canary" not in strategy


def test_build_rollout_manifest_canary_default_steps():
    manifest = build_rollout_manifest(
        _fake_app(),
        target_namespace="acme-production",
        image_tag="v1.2.3",
        strategy="canary",
    )
    strategy = manifest["spec"]["strategy"]
    assert "canary" in strategy
    steps = strategy["canary"]["steps"]
    assert steps == DEFAULT_CANARY_STEPS
    assert any("setWeight" in s for s in steps)


def test_build_rollout_manifest_rolling_raises():
    with pytest.raises(ValueError, match="Rolling"):
        build_rollout_manifest(
            _fake_app(),
            target_namespace="acme-dev",
            image_tag="v1.0.0",
            strategy="rolling",
        )


@pytest.mark.asyncio
async def test_check_rollouts_available_caches_result():
    # Reset cache for this test.
    rollout_service._rollouts_available_cache.clear()

    fake_api = MagicMock()
    fake_api.read_custom_resource_definition.return_value = {"ok": True}
    with patch(
        "app.services.rollout_service._apiextensions_api",
        return_value=fake_api,
    ) as patched:
        assert await check_rollouts_available("beck-prod") is True
        assert await check_rollouts_available("beck-prod") is True

    # Second call should have been served from the module-level cache.
    assert patched.call_count == 1
    assert fake_api.read_custom_resource_definition.call_count == 1
    rollout_service._rollouts_available_cache.clear()
