"""REST door for the existing MCP lifecycle transition."""

import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.api.dependencies import get_current_user, get_user_db_url
from src.models.user import UserInfo
from toon import decode

router = APIRouter(prefix="/projects/{name}/contexts", tags=["Contexts"])


class LifecycleRequest(BaseModel):
    state: Literal["active", "parked", "delivered", "archived"]
    review_after_days: Optional[int] = None
    note: Optional[str] = None


@router.post("/{topic}/lifecycle")
async def transition_context(
    name: str,
    topic: str,
    body: LifecycleRequest,
    user: UserInfo = Depends(get_current_user),
    db_url: str = Depends(get_user_db_url),
):
    from src.api.routes.projects import _resolve_project_db
    from stompy_server import set_lifecycle

    _resolve_project_db(user, name, db_url, require_write=True, with_access=True)
    raw = await set_lifecycle(
        topic=topic,
        state=body.state,
        project=name,
        review_after_days=body.review_after_days,
        note=body.note,
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = decode(raw)
    if payload.get("success") is False or payload.get("error"):
        code = payload.get("error")
        status = {
            "CONTEXT_NOT_FOUND": 404,
            "ACCESS_DENIED": 403,
            "INVALID_PROJECT": 404,
        }.get(code, 503)
        raise HTTPException(status_code=status, detail=payload)
    return payload
