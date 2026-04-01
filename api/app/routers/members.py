import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user
from app.schemas.team import MemberCreate, MemberResponse, MemberUpdate
from app.services import audit_service, member_service, team_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teams/{slug}/members", tags=["members"])


class TransferOwnershipRequest(BaseModel):
    email: str


def _member_to_response(member) -> MemberResponse:
    return MemberResponse(
        email=member.email,
        keycloakId=member.keycloak_id,
        role=member.role,
        addedAt=member.added_at,
    )


async def _check_team_admin(slug: str, user: CurrentUser, db: AsyncSession) -> None:
    if "admin" in user.roles:
        return
    team = await team_service.get_team(db, slug)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.owner_email == user.email:
        return
    for m in (team.members or []):
        if m.email == user.email and m.role == "admin":
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to manage members of this team",
    )


async def _sync_team_crd(slug: str, db: AsyncSession) -> None:
    team = await team_service.get_team(db, slug)
    if team is not None:
        try:
            k8s_service.apply_team_crd(team, team.members)
        except Exception:
            logger.warning("Failed to sync Team CRD for '%s'", slug, exc_info=True)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MemberResponse)
async def add_member(
    slug: str,
    data: MemberCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemberResponse:
    await _check_team_admin(slug, user, db)

    try:
        member = await member_service.add_member(db, slug, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="add_member",
        resource_type="team_member",
        resource_id=data.email,
        team_slug=slug,
        request_body=data.model_dump(),
        response_status=201,
    )

    await _sync_team_crd(slug, db)
    return _member_to_response(member)


@router.get("", response_model=list[MemberResponse])
async def list_members(
    slug: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MemberResponse]:
    try:
        members = await member_service.list_members(db, slug)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [_member_to_response(m) for m in members]


@router.patch("/{email}", response_model=MemberResponse)
async def update_member_role(
    slug: str,
    email: str,
    data: MemberUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemberResponse:
    await _check_team_admin(slug, user, db)

    try:
        member = await member_service.update_member_role(db, slug, email, data.role)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="update_member_role",
        resource_type="team_member",
        resource_id=email,
        team_slug=slug,
        request_body=data.model_dump(),
        response_status=200,
    )

    await _sync_team_crd(slug, db)
    return _member_to_response(member)


@router.delete("/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    slug: str,
    email: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _check_team_admin(slug, user, db)

    try:
        await member_service.remove_member(db, slug, email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="remove_member",
        resource_type="team_member",
        resource_id=email,
        team_slug=slug,
        response_status=204,
    )

    await _sync_team_crd(slug, db)


transfer_router = APIRouter(prefix="/api/v1/teams/{slug}", tags=["members"])


@transfer_router.post("/transfer-ownership")
async def transfer_ownership(
    slug: str,
    data: TransferOwnershipRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await _check_team_admin(slug, user, db)

    try:
        team = await member_service.transfer_ownership(db, slug, data.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="transfer_ownership",
        resource_type="team",
        resource_id=str(team.id),
        team_slug=slug,
        request_body=data.model_dump(),
        response_status=200,
    )

    await _sync_team_crd(slug, db)
    return {"message": f"Ownership transferred to {data.email}"}
