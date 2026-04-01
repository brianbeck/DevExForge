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
