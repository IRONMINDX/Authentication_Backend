import math
import uuid

from fastapi import APIRouter, Query

from app.dependencies.auth import CurrentUser, RequireAdmin
from app.dependencies.services import UserServiceDep
from app.schemas.user import UserRead, UserUpdate
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead, summary="Get the current authenticated user's profile")
async def get_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead, summary="Update the current user's profile")
async def update_me(
    payload: UserUpdate, current_user: CurrentUser, user_service: UserServiceDep
) -> UserRead:
    updated = await user_service.update_profile(current_user, payload)
    return UserRead.model_validate(updated)


@router.get(
    "",
    response_model=PaginatedResponse[UserRead],
    summary="List users (admin only)",
)
async def list_users(
    _: RequireAdmin,
    user_service: UserServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[UserRead]:
    offset = (page - 1) * page_size
    users, total = await user_service.list_users(offset=offset, limit=page_size)
    return PaginatedResponse[UserRead](
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{user_id}", response_model=UserRead, summary="Get a user by ID (admin only)")
async def get_user(
    user_id: uuid.UUID, _: RequireAdmin, user_service: UserServiceDep
) -> UserRead:
    user = await user_service.get_by_id(user_id)
    return UserRead.model_validate(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    summary="Deactivate a user account (admin only)",
)
async def deactivate_user(
    user_id: uuid.UUID, current_user: RequireAdmin, user_service: UserServiceDep
) -> UserRead:
    target = await user_service.deactivate_user(current_user, user_id)
    return UserRead.model_validate(target)
