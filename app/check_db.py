"""Скрипт для проверки содержимого базы данных.
Запуск: python -m app.check_db
"""
from .database import SessionLocal
from .models import (
    Client, ClientProfile, BankAnalytic, DocumentChunk, 
    EventInsight, AnalysisRun
)

def check_db():
    db = SessionLocal()
    print("=" * 50)
    print("📊 СТАТИСТИКА БАЗЫ ДАННЫХ")
    print("=" * 50)

    clients_count = db.query(Client).count()
    profiles_count = db.query(ClientProfile).count()
    print(f"👥 Клиентов в базе: {clients_count}")
    
    pdfs_count = db.query(BankAnalytic).count()
    chunks_count = db.query(DocumentChunk).count()
    print(f"📄 PDF-отчетов загружено: {pdfs_count}")
    print(f"🧩 Чанков (кусков текста для RAG): {chunks_count}")
    
    runs_count = db.query(AnalysisRun).count()
    insights_count = db.query(EventInsight).count()
    print(f"🤖 Запусков AI-анализа: {runs_count}")
    print(f"💡 Сгенерировано инсайтов (риски/возможности): {insights_count}")

    print("\n" + "=" * 50)
    print("📄 ПОСЛЕДНИЕ ЗАГРУЖЕННЫЕ PDF:")
    print("=" * 50)
    for p in db.query(BankAnalytic).order_by(BankAnalytic.id.desc()).limit(5).all():
        print(f"- {p.title} (Категория: {p.category})")
        print(f"  Текст (первые 100 символов): {p.body[:100]}...")

    print("\n" + "=" * 50)
    print("💡 ПОСЛЕДНИЕ СГЕНЕРИРОВАННЫЕ ИНСАЙТЫ:")
    print("=" * 50)
    if insights_count == 0:
        print("❌ ИНСАЙТОВ НЕТ. Возможно, скрипт generate_insights.py не запускался или упал с ошибкой.")
    else:
        for ins in db.query(EventInsight).order_by(EventInsight.id.desc()).limit(5).all():
            impact = ins.impact or {}
            kind = impact.get("kind", "unknown")
            emoji = "🔴" if kind == "risk" else "🟢" if kind == "opportunity" else "⚪"
            
            print(f"{emoji} [{kind.upper()}] {ins.title}")
            print(f"   Уверенность: {impact.get('confidence', 0)} | Релевантность: {ins.relevance_score}")
            print(f"   Механизм влияния: {impact.get('mechanism', 'Нет описания')[:150]}...")
            print(f"   Рекомендация: {impact.get('recommended_actions', ['Нет'])[0]}")
            print("-" * 40)

    db.close()

if __name__ == "__main__":
    check_db()