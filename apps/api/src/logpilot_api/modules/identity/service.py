"""Identity business logic for registration, credential verification, and token issuance."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.config import get_settings
from logpilot_api.core.errors import ConflictError, UnauthorizedError
from logpilot_api.core.security import create_access_token, hash_password, verify_password
from logpilot_api.modules.identity.models import User
from logpilot_api.modules.identity.repository import UserRepository
from logpilot_api.modules.identity.schemas import UserLoginRequest, UserRegisterRequest


class IdentityService:
    """Service orchestrating user accounts and authentication."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def register_user(self, payload: UserRegisterRequest) -> User:
        """Register a new user account with Argon2id password hashing."""
        existing = await self.repo.get_by_email(payload.email)
        if existing:
            raise ConflictError(
                message="An account with this email address already exists.",
                code="EMAIL_ALREADY_EXISTS",
            )

        password_hash = hash_password(payload.password)
        try:
            user = await self.repo.create(
                email=payload.email,
                password_hash=password_hash,
                full_name=payload.full_name,
            )
            await self.session.commit()
            return user
        except IntegrityError as exc:
            await self.session.rollback()
            err_msg = (
                str(exc.orig).lower() if hasattr(exc, "orig") and exc.orig else str(exc).lower()
            )
            if "uq_users_email" in err_msg or "users.email" in err_msg or "email" in err_msg:
                raise ConflictError(
                    message="An account with this email address already exists.",
                    code="EMAIL_ALREADY_EXISTS",
                ) from exc
            raise

    async def authenticate_user(self, payload: UserLoginRequest) -> tuple[str, int, User]:
        """Authenticate user credentials and issue an HS256 JWT bearer token."""
        user = await self.repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError(
                message="Invalid email or password.",
                code="UNAUTHORIZED",
            )

        if not user.is_active:
            raise UnauthorizedError(
                message="User account is inactive.",
                code="UNAUTHORIZED",
            )

        settings = get_settings()
        token = create_access_token(user.id, user.email)
        expires_in = settings.access_token_expire_minutes * 60
        return token, expires_in, user
