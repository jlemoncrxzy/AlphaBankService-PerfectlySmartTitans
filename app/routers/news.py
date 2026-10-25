from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import NewsItem, BankAnalytic, User
from ..schemas import AnalyticOut
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["content"])

@router.get("/news")
def list_news(limit: int = Query(50, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Возвращает объединенный список: новости + загруженные PDF-файлы."""
    news = db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(limit).all()
    pdfs = db.query(BankAnalytic).order_by(BankAnalytic.published_at.desc()).limit(limit).all()
    
    result = []
    for n in news:
        result.append({
            "id": n.id, "type": "news", "title": n.title, "body": n.body,
            "source": n.source, "published_at": n.published_at.isoformat(),
            "magnitude": n.magnitude
        })
    for p in pdfs:
        result.append({
            "id": p.id, "type": "pdf", "title": p.title, "body": p.body,
            "source": f"Альфа-Банк ({p.category})", "published_at": p.published_at.isoformat(),
            "magnitude": p.magnitude
        })
    
    # Сортируем по дате (сначала свежие)
    result.sort(key=lambda x: x["published_at"], reverse=True)
    return result[:limit]

@router.get("/analytics", response_model=list[AnalyticOut])
def list_analytics(limit: int = Query(20, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(BankAnalytic).order_by(BankAnalytic.published_at.desc()).limit(limit).all()