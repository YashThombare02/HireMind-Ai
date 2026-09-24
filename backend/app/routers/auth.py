from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_users.authentication import JWTStrategy
from fastapi_users.exceptions import InvalidPasswordException, UserAlreadyExists
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth.users import UserManager, get_jwt_strategy, get_user_manager
from app.rate_limit import limiter
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be blank.")
        return stripped


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Custom register/login routes instead of fastapi-users' auto-mounted routers:
# (1) so @limiter.limit(...) can be attached at all — you can't decorate a
#     route function inside a library-built router, and (2) so login accepts
#     plain JSON {email, password} instead of the library default's
#     application/x-www-form-urlencoded OAuth2PasswordRequestForm. Everything
#     else (password hashing, JWT issuance, current_active_user) still goes
#     through fastapi-users' UserManager/auth backend unchanged.


@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await user_manager.create(
            UserCreate(email=payload.email.lower(), password=payload.password, name=payload.name),
            safe=True,
        )
    except UserAlreadyExists as exc:
        raise HTTPException(status_code=400, detail="An account with this email already exists.") from exc
    except InvalidPasswordException as exc:
        raise HTTPException(status_code=400, detail=str(exc.reason)) from exc
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    user_manager: UserManager = Depends(get_user_manager),
    strategy: JWTStrategy = Depends(get_jwt_strategy),
):
    # user_manager.authenticate() only reads .username/.password off its
    # argument despite being typed for OAuth2PasswordRequestForm, so a
    # SimpleNamespace with those two attributes satisfies it at runtime.
    credentials = SimpleNamespace(username=payload.email.lower(), password=payload.password)
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        # Same generic message for "no such user" and "wrong password" —
        # never reveal which one it was (avoids user enumeration).
        raise HTTPException(status_code=400, detail="Invalid email or password.")
    token = await strategy.write_token(user)
    return TokenResponse(access_token=token)
