from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.users import UserManager, current_active_user, get_user_manager
from app.db.models import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


class UpdateMeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.get("/me", response_model=UserRead)
async def read_me(user: User = Depends(current_active_user)):
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UpdateMeRequest,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    return await user_manager.update(UserUpdate(name=payload.name.strip()), user)
