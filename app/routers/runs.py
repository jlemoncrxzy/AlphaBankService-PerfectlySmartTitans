from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AnalysisRun, ToolLog, User
from ..schemas import RunOut, RunDetail, ToolLogOut
from ..security import get_current_user, require_role

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(50).all()


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    r = db.get(AnalysisRun, run_id)
    if not r:
        raise HTTPException(404, "Run не найден")
    return r


@router.get("/{run_id}/tools", response_model=list[ToolLogOut])
def get_run_tools(run_id: int, db: Session = Depends(get_db),
                  user: User = Depends(require_role("admin", "analyst"))):
    """Журнал обращений к инструментам в рамках run — для аудита."""
    return db.query(ToolLog).filter(ToolLog.run_id == run_id) \
             .order_by(ToolLog.created_at).all()


@router.get("_admin/tools", response_model=list[ToolLogOut], include_in_schema=False)
def all_tools(db: Session = Depends(get_db),
              user: User = Depends(require_role("admin"))):
    return db.query(ToolLog).order_by(ToolLog.created_at.desc()).limit(200).all()