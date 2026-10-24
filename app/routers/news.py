from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import NewsItem, BankAnalytic, User
from ..schemas import NewsOut, AnalyticOut
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["content"])


@router.get("/news", response_model=list[NewsOut])
def list_news(limit: int = Query(20, le=100), db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    return db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(limit).all()


@router.get("/analytics", response_model=list[AnalyticOut])
def list_analytics(limit: int = Query(20, le=100), db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return db.query(BankAnalytic).order_by(BankAnalytic.published_at.desc()).limit(limit).all()