"""Скрипт для пакетного запуска AI-анализа по всем клиентам в базе."""
from .database import SessionLocal
from .models import Client, AnalysisRun
from .agent.pipeline import run_pipeline_task

def run_all():
    db = SessionLocal()
    clients = db.query(Client).limit(5).all()  # Берем первых 5 клиентов для теста
    print(f"Запускаем анализ для {len(clients)} клиентов...")

    for client in clients:
        print(f"Анализ клиента: {client.name}")
        run = AnalysisRun(client_id=client.id, user_id=1, status="pending")
        db.add(run)
        db.commit()
        
        # Запускаем пайплайн синхронно
        run_pipeline_task(run.id)
        print(f"  -> Готово. Найдено инсайтов.")

    db.close()
    print("✅ Все инсайты сгенерированы и сохранены в БД!")

if __name__ == "__main__":
    run_all()