"""Shared fixtures for DevExForge API tests.

Uses an in-process async SQLite database, mocked Keycloak auth, and mocked
K8s service so the full test suite runs without external dependencies.
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Patch K8sService before any app module is imported.  The module-level
# ``k8s_service = K8sService()`` in app.services.k8s_service tries to connect
# to real clusters on import, so we must intercept it early.
# ---------------------------------------------------------------------------
_mock_k8s_class = MagicMock()
_mock_k8s_instance = MagicMock()
_mock_k8s_instance.apply_team_crd.return_value = {}
_mock_k8s_instance.delete_team_crd.return_value = None
_mock_k8s_instance.apply_environment_crd.return_value = {}
_mock_k8s_instance.delete_environment_crd.return_value = None
_mock_k8s_instance.cluster_for_tier.side_effect = lambda tier: {
    "dev": "beck-stage",
    "staging": "beck-stage",
    "production": "beck-prod",
}.get(tier, "beck-stage")
_mock_k8s_instance.create_argo_application.side_effect = lambda cluster, ns, body: body
_mock_k8s_instance.list_argo_applications.return_value = []
_mock_k8s_instance.delete_argo_application.return_value = None
_mock_k8s_instance.get_argo_application_health.return_value = None
_mock_k8s_class.return_value = _mock_k8s_instance

patch("app.services.k8s_service.K8sService", _mock_k8s_class).start()

# ---------------------------------------------------------------------------
# SQLite compatibility: PostgreSQL-specific column types (JSONB, UUID) are not
# understood by SQLite.  We register compilation hooks so that SQLAlchemy emits
# TEXT / CHAR(32) instead when targeting sqlite.
# ---------------------------------------------------------------------------
from sqlalchemy import BigInteger, Integer, event  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(32)"


# PG_UUID's bind_processor assumes values are uuid.UUID instances and calls
# ``value.hex``. Production code sometimes passes string UUIDs (e.g. the
# refresh flow stringifies the id). Override bind_processor to coerce strings.
import uuid as _uuid  # noqa: E402

_original_pg_uuid_bind_processor = PG_UUID.bind_processor


def _tolerant_bind_processor(self, dialect):
    inner = _original_pg_uuid_bind_processor(self, dialect)

    def process(value):
        if isinstance(value, str):
            try:
                value = _uuid.UUID(value)
            except (ValueError, TypeError):
                return value
        if inner is None:
            return value
        return inner(value)

    return process


PG_UUID.bind_processor = _tolerant_bind_processor


# SQLite only auto-generates values for INTEGER (not BIGINT) primary keys.
# Swap BigInteger -> Integer in the audit_log table so autoincrement works.
@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):
    return "INTEGER"


# Now it is safe to import the app -----------------------------------------
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from app.database import Base, get_db  # noqa: E402
from app.middleware.auth import CurrentUser, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

# Test database URL - SQLite async in-memory
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    """Create a test database engine with all tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a test database session."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_test_user(
    email: str = "admin@company.com",
    keycloak_id: str = "test-admin-id",
    roles: list[str] | None = None,
) -> CurrentUser:
    """Create a ``CurrentUser`` for testing."""
    if roles is None:
        roles = ["admin", "team-leader"]
    return CurrentUser(email=email, keycloak_id=keycloak_id, roles=roles)


# ---------------------------------------------------------------------------
# HTTP client fixtures
# ---------------------------------------------------------------------------

def _build_db_override(engine):
    """Return an async generator that overrides ``get_db``."""
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return override_get_db


def _setup_overrides(engine, user: CurrentUser):
    """Install FastAPI dependency overrides for db + auth."""
    import app.services.k8s_service as k8s_mod

    mock_k8s = MagicMock()
    mock_k8s.apply_team_crd.return_value = {}
    mock_k8s.delete_team_crd.return_value = None
    mock_k8s.apply_environment_crd.return_value = {}
    mock_k8s.delete_environment_crd.return_value = None
    mock_k8s.cluster_for_tier.side_effect = lambda tier: {
        "dev": "beck-stage",
        "staging": "beck-stage",
        "production": "beck-prod",
    }.get(tier, "beck-stage")
    mock_k8s.create_argo_application.side_effect = lambda cluster, ns, body: body
    mock_k8s.list_argo_applications.return_value = []
    mock_k8s.delete_argo_application.return_value = None
    mock_k8s.get_argo_application_health.return_value = None

    original_k8s = k8s_mod.k8s_service
    k8s_mod.k8s_service = mock_k8s

    app.dependency_overrides[get_db] = _build_db_override(engine)

    async def override_get_current_user():
        return user

    # Override get_current_user.  Because require_role() uses
    #   Depends(get_current_user)
    # FastAPI's dependency injection will pick up this override automatically.
    app.dependency_overrides[get_current_user] = override_get_current_user

    return original_k8s


def _teardown_overrides(original_k8s):
    import app.services.k8s_service as k8s_mod

    app.dependency_overrides.clear()
    k8s_mod.k8s_service = original_k8s


@pytest.fixture(autouse=True)
def _install_k8s_mock_everywhere():
    """Swap the real ``k8s_service`` binding for a MagicMock in every module
    that imported it at load time. Without this, services that did
    ``from app.services.k8s_service import k8s_service`` would still reference
    the real ``K8sService`` instance created during module import, and tests
    would hit ``RuntimeError: No Kubernetes client configured``.
    """
    import sys
    mk = _mock_k8s_instance

    # Reset and reinstall defaults before each test
    mk.reset_mock()
    mk.apply_team_crd.return_value = {}
    mk.delete_team_crd.return_value = None
    mk.apply_environment_crd.return_value = {}
    mk.delete_environment_crd.return_value = None
    mk.cluster_for_tier.side_effect = lambda tier: {
        "dev": "beck-stage",
        "staging": "beck-stage",
        "production": "beck-prod",
    }.get(tier, "beck-stage")
    mk.create_argo_application.side_effect = lambda cluster, ns, body: body
    mk.list_argo_applications.return_value = []
    mk.list_argo_applications.side_effect = None
    mk.delete_argo_application.return_value = None
    mk.delete_argo_application.side_effect = None
    mk.get_argo_application_health.return_value = None
    mk.get_argo_application_health.side_effect = None

    originals: dict[str, object] = {}
    for mod_name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if not mod_name.startswith("app."):
            continue
        if getattr(mod, "k8s_service", None) is None:
            continue
        # Only swap bindings that came from app.services.k8s_service
        if mod_name == "app.services.k8s_service":
            continue
        originals[mod_name] = mod.k8s_service
        mod.k8s_service = mk
    # Also the canonical module
    import app.services.k8s_service as k_mod
    originals["app.services.k8s_service"] = k_mod.k8s_service
    k_mod.k8s_service = mk

    yield mk

    for mod_name, orig in originals.items():
        mod = sys.modules.get(mod_name)
        if mod is not None:
            mod.k8s_service = orig


@pytest.fixture
def mock_k8s():
    """Access to the shared K8sService mock used by all services.

    Resets call history and restores default return values on each test so
    tests can freely assert on calls and override return values without
    polluting other tests.
    """
    mk = _mock_k8s_instance
    mk.reset_mock()
    # Restore defaults (reset_mock clears side_effect/return_value if we asked,
    # but we want to re-establish them regardless).
    mk.apply_team_crd.return_value = {}
    mk.delete_team_crd.return_value = None
    mk.apply_environment_crd.return_value = {}
    mk.delete_environment_crd.return_value = None
    mk.cluster_for_tier.side_effect = lambda tier: {
        "dev": "beck-stage",
        "staging": "beck-stage",
        "production": "beck-prod",
    }.get(tier, "beck-stage")
    mk.create_argo_application.side_effect = lambda cluster, ns, body: body
    mk.list_argo_applications.return_value = []
    mk.list_argo_applications.side_effect = None
    mk.delete_argo_application.return_value = None
    mk.delete_argo_application.side_effect = None
    mk.get_argo_application_health.return_value = None
    mk.get_argo_application_health.side_effect = None
    yield mk


@pytest_asyncio.fixture
async def client(db_engine):
    """Async test client authenticated as an **admin** user."""
    admin_user = make_test_user()
    original_k8s = _setup_overrides(db_engine, admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    _teardown_overrides(original_k8s)


@pytest_asyncio.fixture
async def teamlead_client(db_engine):
    """Async test client authenticated as a **team-leader** (not admin)."""
    teamlead_user = make_test_user(
        email="teamlead1@company.com",
        keycloak_id="test-teamlead-id",
        roles=["team-leader"],
    )
    original_k8s = _setup_overrides(db_engine, teamlead_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    _teardown_overrides(original_k8s)


@pytest_asyncio.fixture
async def developer_client(db_engine):
    """Async test client authenticated as a **developer** (no special roles)."""
    dev_user = make_test_user(
        email="developer1@company.com",
        keycloak_id="test-dev-id",
        roles=[],
    )
    original_k8s = _setup_overrides(db_engine, dev_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    _teardown_overrides(original_k8s)
