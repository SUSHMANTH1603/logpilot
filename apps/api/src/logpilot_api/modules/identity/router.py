"""Authentication and user management route endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.api.deps import get_session
from logpilot_api.modules.identity.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from logpilot_api.modules.identity.service import IdentityService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new developer account",
)
async def register(
    payload: UserRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Register a new user account with Argon2id password hashing."""
    service = IdentityService(session)
    user = await service.register_user(payload)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive access token",
)
async def login(
    payload: UserLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Authenticate email and password and return a signed HS256 JWT bearer token."""
    service = IdentityService(session)
    token, expires_in, user = await service.authenticate_user(payload)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )
