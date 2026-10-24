from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Client, AnalysisRun, User
from ..schemas import ClientOut, ClientBrief, ClientListOut
from ..security import get_current_user, require_role
from ..agent.pipeline import run_pipeline_task
from ..config import settings

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("", response_model=ClientListOut)
def list_clients(
    page: int = Query(1, ge=1), 
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user)
):
    """Возвращает клиентов постранично. По умолчанию 20 на страницу."""
    total = db.query(Client).count()
    items = db.query(Client).order_by(Client.name).offset((page - 1) * size).limit(size).all()
    return ClientListOut(items=items, total=total, page=page, size=size)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(404, "Клиент не найден")
    return c


@router.post("/{client_id}/analyze")
def analyze(client_id: int, background: BackgroundTasks,
            db: Session = Depends(get_db),
            user: User = Depends(require_role("admin", "analyst"))):
    """Запуск многошагового AI-анализа."""
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(404, "Клиент не найден")
    run = AnalysisRun(client_id=c.id, user_id=user.id, status="pending", model=settings.llm_model)
    db.add(run); db.commit(); db.refresh(run)
    background.add_task(run_pipeline_task, run.id)
    return {"run_id": run.id, "status": "pending"}