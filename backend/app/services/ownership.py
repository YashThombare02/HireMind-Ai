import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_owned_or_404(session: AsyncSession, model, obj_id: uuid.UUID, user_id: uuid.UUID):
    """Ownership check done as part of the query itself (WHERE id=... AND
    user_id=...), not fetch-then-check in Python — and 404, never 403, so a
    valid id belonging to someone else never confirms its own existence.
    See docs/ARCHITECTURE.md "Ownership and auth".
    """
    stmt = select(model).where(model.id == obj_id, model.user_id == user_id)
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return obj
