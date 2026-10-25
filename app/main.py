"""Точка входа FastAPI."""
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import settings
from .database import Base, engine
from .seed import seed
from .routers import auth, clients, news, runs, dashboard, reports

app = FastAPI(title=settings.app_name, version="0.1.0")

@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    seed()

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(news.router)
app.include_router(runs.router)
app.include_router(dashboard.router) # <--- Роутер для React-дашборда
app.include_router(reports.router)  # <--- Выгрузка DOCX-отчёта по компании

# Раздача статики React
if os.path.exists("frontend/dist/assets"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
if os.path.exists("frontend/dist/icons"):
    app.mount("/icons", StaticFiles(directory="frontend/dist/icons"), name="icons")

@app.get("/promo-analytics.png", include_in_schema=False)
def promo_art():
    return FileResponse("frontend/dist/promo-analytics.png")

@app.get("/", include_in_schema=False)
def index():
    if os.path.exists("frontend/dist/index.html"):
        return FileResponse("frontend/dist/index.html")
    return {"error": "Frontend not built. Run 'npm run build' in 'frontend' folder."}

@app.get("/health")
def health():
    return {"status": "ok", "model": settings.llm_model, "provider": settings.llm_provider}