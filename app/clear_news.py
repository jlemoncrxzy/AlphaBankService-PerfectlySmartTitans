from .database import SessionLocal
from .models import NewsItem

def clear_news():
    db = SessionLocal()
    deleted = db.query(NewsItem).delete()
    db.commit()
    db.close()
    print(f"Удалено {deleted} старых новостей. Теперь в базе только PDF-аналитика!")

if __name__ == "__main__":
    clear_news()