import logging
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()

_jwks_cache: dict | None = None


@dataclass
class CurrentUser:
    email: str
    keycloak_id: str
    roles: list[str] = field(default_factory=list)


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    well_known_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/.well-known/openid-configuration"
    )
    async with httpx.AsyncClient() as client:
        oidc_response = await client.get(well_known_url, timeout=10.0)
        oidc_response.raise_for_status()
        oidc_config = oidc_response.json()

        jwks_uri = oidc_config["jwks_uri"]
        jwks_response = await client.get(jwks_uri, timeout=10.0)
        jwks_response.raise_for_status()
        _jwks_cache = jwks_response.json()

    return _jwks_cache


def _extract_roles(payload: dict) -> list[str]:
    roles: list[str] = []
    realm_access = payload.get("realm_access", {})
    if isinstance(realm_access, dict):
        roles.extend(realm_access.get("roles", []))
    resource_access = payload.get("resource_access", {})
    client_roles = resource_access.get(settings.KEYCLOAK_CLIENT_ID, {})
    if isinstance(client_roles, dict):
        roles.extend(client_roles.get("roles", []))
    return roles


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    token = credentials.credentials

    try:
        jwks = await _get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        rsa_key: dict = {}
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate signing key",
            )

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            issuer=f"{settings.KEYCLOAK_ISSUER_URL or settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}",
        )

        email = payload.get("email")
        keycloak_id = payload.get("sub")

        if not email or not keycloak_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required claims",
            )

        roles = _extract_roles(payload)

        return CurrentUser(email=email, keycloak_id=keycloak_id, roles=roles)

    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from e
    except httpx.HTTPError as e:
        logger.error("Failed to fetch JWKS: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from e


def require_role(role: str):
    async def _check_role(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if role not in user.roles and "admin" not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required",
            )
        return user

    return _check_role
