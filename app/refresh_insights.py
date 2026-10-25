"""Перегенерация AI-инсайтов для клиентов, у которых уже были запуски.

Нужна после переиндексации PDF/новостей: старые инсайты хранят source_id,
который после перезаписи таблиц-источников может указывать на другой документ.
Скрипт создаёт по одному новому запуску на каждого такого клиента.

Запуск: python -m app.refresh_insights
"""
from .agent.pipeline import run_pipeline_task
from .config import settings
from .database import SessionLocal
from .models import AnalysisRun, User


def run() -> None:
    db = SessionLocal()
    try:
        client_ids = sorted({row[0] for row in db.query(AnalysisRun.client_id).distinct().all()})
        user = (
            db.query(User)
            .filter(User.role.in_(("analyst", "admin")))
            .order_by(User.id)
            .first()
            or db.query(User).order_by(User.id).first()
        )
        if user is None:
            raise RuntimeError("В базе нет пользователей")

        run_ids = []
        for client_id in client_ids:
            analysis_run = AnalysisRun(
                client_id=client_id,
                user_id=user.id,
                status="pending",
                model=settings.llm_model,
            )
            db.add(analysis_run)
            db.commit()
            db.refresh(analysis_run)
            run_ids.append(analysis_run.id)
            print(f"Клиент {client_id}: создан запуск #{analysis_run.id}")
    finally:
        db.close()

    for run_id in run_ids:
        run_pipeline_task(run_id)
        print(f"Запуск #{run_id}: готово")

    print(f"Перегенерировано запусков: {len(run_ids)}")


if __name__ == "__main__":
    run()
