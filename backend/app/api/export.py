import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Comment, User, Game
from app.auth import get_current_user

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/generate/{task_id}")
async def generate_report(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Trigger report generation for a pending task."""
    from app.models import ReportTask
    result = await db.execute(select(ReportTask).where(ReportTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Report task not found")

    # Fetch comments
    q = select(Comment).join(Game).order_by(Comment.published_at.desc())
    if task.game_id:
        q = q.where(Comment.game_id == task.game_id)
    rows = (await db.execute(q)).scalars().all()

    if task.type == "excel":
        from app.utils.exporter import export_excel
        file_path = export_excel(task, rows)
    else:
        from app.utils.exporter import export_pdf
        file_path = export_pdf(task, rows)

    task.status = "done"
    task.file_path = file_path
    await db.flush()
    return {"status": "done", "file_path": file_path}
