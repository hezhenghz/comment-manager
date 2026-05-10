import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ReportTask, User
from app.auth import get_current_user
from app.schemas.schemas import ReportTaskCreate, ReportTaskOut

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=list[ReportTaskOut])
async def list_reports(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ReportTask).order_by(ReportTask.created_at.desc()))
    return [ReportTaskOut.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=ReportTaskOut, status_code=status.HTTP_201_CREATED)
async def create_report(body: ReportTaskCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    date_range = f"{body.date_from or ''}/{body.date_to or ''}" if body.date_from or body.date_to else None
    task = ReportTask(game_id=body.game_id, type=body.type, date_range=date_range, schedule=body.schedule)
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return ReportTaskOut.model_validate(task)


@router.get("/{task_id}/download")
async def download_report(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ReportTask).where(ReportTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None or task.status != "done" or not task.file_path:
        raise HTTPException(status_code=404, detail="Report not available")
    return FileResponse(task.file_path, filename=f"report-{task.id}.{task.type.lower()}")
