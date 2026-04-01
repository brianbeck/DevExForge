import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user, require_role
from app.schemas.team import TeamCreate, TeamListResponse, TeamResponse, TeamUpdate
from app.services import audit_service, team_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


def _team_to_response(team) -> TeamResponse:
    return TeamResponse(
        id=team.id,
        slug=team.slug,
        displayName=team.display_name,
        description=team.description,
        costCenter=team.cost_center,
        tags=team.tags,
        ownerEmail=team.owner_email,
        createdAt=team.created_at,
        updatedAt=team.updated_at,
        memberCount=len(team.members) if team.members else 0,
        environmentCount=len(team.environments) if team.environments else 0,
    )


def _check_team_permission(team, user: CurrentUser) -> None:
    if "admin" in user.roles:
        return
    if team.owner_email == user.email:
        return
    for m in (team.members or []):
        if m.email == user.email and m.role == "admin":
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to modify this team",
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TeamResponse)
async def create_team(
    data: TeamCreate,
    user: Annotated[CurrentUser, Depends(require_role("team-leader"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    team = await team_service.create_team(db, user, data)
    await db.flush()

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="create",
        resource_type="team",
        resource_id=str(team.id),
        team_slug=team.slug,
        request_body=data.model_dump(by_alias=True),
        response_status=201,
    )

    try:
        k8s_service.apply_team_crd(team, team.members)
    except Exception:
        logger.warning("Failed to sync Team CRD for '%s'", team.slug, exc_info=True)

    return _team_to_response(team)


@router.get("", response_model=TeamListResponse)
async def list_teams(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamListResponse:
    teams = await team_service.list_teams(db, user)
    return TeamListResponse(
        teams=[_team_to_response(t) for t in teams],
        total=len(teams),
    )


@router.get("/{slug}", response_model=TeamResponse)
async def get_team(
    slug: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    team = await team_service.get_team(db, slug)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return _team_to_response(team)


@router.patch("/{slug}", response_model=TeamResponse)
async def update_team(
    slug: str,
    data: TeamUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    team = await team_service.get_team(db, slug)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    _check_team_permission(team, user)

    team = await team_service.update_team(db, slug, data)

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="update",
        resource_type="team",
        resource_id=str(team.id),
        team_slug=team.slug,
        request_body=data.model_dump(by_alias=True, exclude_none=True),
        response_status=200,
    )

    try:
        k8s_service.apply_team_crd(team, team.members)
    except Exception:
        logger.warning("Failed to sync Team CRD for '%s'", team.slug, exc_info=True)

    return _team_to_response(team)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    slug: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    team = await team_service.get_team(db, slug)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    _check_team_permission(team, user)

    team_id = str(team.id)
    await team_service.delete_team(db, slug)

    await audit_service.log_action(
        db,
        user_email=user.email,
        action="delete",
        resource_type="team",
        resource_id=team_id,
        team_slug=slug,
        response_status=204,
    )

    try:
        k8s_service.delete_team_crd(slug)
    except Exception:
        logger.warning("Failed to delete Team CRD for '%s'", slug, exc_info=True)
