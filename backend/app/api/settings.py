from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings(_: User = Depends(get_current_user)):
    return {"message": "Settings endpoint placeholder"}
