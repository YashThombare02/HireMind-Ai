import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.db.session import get_async_session

logger = logging.getLogger("hireminds.auth")


async def get_user_db(session: AsyncSession = Depends(get_async_session)) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    # fastapi-users requires these for its password-reset/email-verification
    # token machinery even though this project doesn't expose those flows
    # (no email sending — out of scope, see docs/ARCHITECTURE.md Module 5).
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        logger.info("user_registered", extra={"user_id": str(user.id)})


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

_current_active_user = fastapi_users.current_user(active=True)


async def current_active_user(
    request: Request,
    user: User = Depends(_current_active_user),
) -> User:
    # Stamped onto request.state so RequestLoggingMiddleware can attribute the
    # log line to a user without every route having to do this itself.
    request.state.user_id = str(user.id)
    return user
