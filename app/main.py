"""Точка входа FastAPI. Поднимает БД, сеет синтетику, подключает роутеры и статику."""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import settings
from .database import Base, engine
from .seed import seed
from .routers import auth, clients, news, runs

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    seed()  # идемпотентно


app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(news.router)
app.include_router(runs.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("app/static/index.html")


@app.get("/health")
def health():
    return {"status": "ok", "model": settings.llm_model, "provider": settings.llm_provider}