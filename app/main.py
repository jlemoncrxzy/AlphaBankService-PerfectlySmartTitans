"""Точка входа FastAPI."""
import logging
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine
from .seed import seed
from .routers import auth, clients, news, runs, dashboard, reports

# Пути считаем от корня проекта, а не от текущей рабочей директории:
# на сервере uvicorn может запускаться из любого каталога.
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
INDEX_FILE = DIST_DIR / "index.html"

# index.html ссылается на хэшированные файлы сборки, поэтому его нельзя кэшировать:
# иначе браузер/CDN отдаёт старый HTML со ссылками на уже удалённые /assets/*.
NO_CACHE = "no-store, no-cache, must-revalidate, max-age=0"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
SHORT_CACHE = "public, max-age=86400"

log = logging.getLogger("uvicorn.error")


class BuildStaticFiles(StaticFiles):
    """StaticFiles с явным Cache-Control (иначе прокси и браузер кэшируют как придётся)."""

    def __init__(self, *args, cache_control: str = IMMUTABLE_CACHE, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_control = cache_control

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = self.cache_control
        return response


def _index_response() -> FileResponse | HTMLResponse:
    if INDEX_FILE.is_file():
        return FileResponse(
            INDEX_FILE,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": NO_CACHE, "Pragma": "no-cache", "Expires": "0"},
        )
    return HTMLResponse(
        "<h1>Frontend не собран</h1>"
        "<p>Выполните <code>npm ci &amp;&amp; npm run build</code> в папке <code>frontend</code> "
        "и перезапустите сервер.</p>",
        status_code=503,
        headers={"Cache-Control": NO_CACHE},
    )


def _check_frontend_build() -> None:
    """Пишем в лог, если index.html ссылается на отсутствующие файлы сборки."""
    if not INDEX_FILE.is_file():
        log.error(
            "frontend/dist/index.html не найден (%s) — UI отдаваться не будет. "
            "Выполните `npm ci && npm run build` в папке frontend.",
            INDEX_FILE,
        )
        return
    html = INDEX_FILE.read_text(encoding="utf-8", errors="ignore")
    referenced = {m for m in re.findall(r'(?:src|href)="(/[^"]+)"', html) if not m.startswith("//")}
    missing = [url for url in sorted(referenced) if not (DIST_DIR / url.lstrip("/")).is_file()]
    if missing:
        log.error(
            "Сборка frontend неполная/устаревшая: index.html ссылается на отсутствующие файлы %s. "
            "Похоже, dist собран из другой версии или файлы не скопированы на сервер — "
            "пересоберите UI (`npm ci && npm run build`) и сбросьте кэш index.html.",
            ", ".join(missing),
        )
    else:
        log.info("Frontend build OK: %s", DIST_DIR)


app = FastAPI(title=settings.app_name, version="0.1.0")

@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    seed()
    _check_frontend_build()

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(news.router)
app.include_router(runs.router)
app.include_router(dashboard.router) # <--- Роутер для React-дашборда
app.include_router(reports.router)  # <--- Выгрузка DOCX-отчёта по компании

# Раздача статики React. Монтируем всегда: если сборки нет — будет аккуратный 404/503,
# а не падение на импорте и не «потерянные» маршруты после пересборки на ходу.
app.mount(
    "/assets",
    BuildStaticFiles(directory=str(DIST_DIR / "assets"), check_dir=False),
    name="assets",
)
app.mount(
    "/icons",
    BuildStaticFiles(directory=str(DIST_DIR / "icons"), check_dir=False, cache_control=SHORT_CACHE),
    name="icons",
)

@app.get("/promo-analytics.png", include_in_schema=False)
def promo_art():
    for candidate in (DIST_DIR / "promo-analytics.png", FRONTEND_DIR / "public" / "promo-analytics.png"):
        if candidate.is_file():
            return FileResponse(candidate, headers={"Cache-Control": SHORT_CACHE})
    raise HTTPException(status_code=404, detail="Not Found")

@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {
        "status": "ok",
        "model": settings.llm_model,
        "provider": settings.llm_provider,
        "frontend_built": INDEX_FILE.is_file(),
    }

# HEAD нужен health-check'ам хостингов (Render шлёт `HEAD /`, иначе 405 в логах).
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def index():
    return _index_response()

@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    """Отдаём прочие файлы сборки (favicon, manifest, ...) и SPA-роутинг на index.html."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    dist_root = DIST_DIR.resolve()
    target = (dist_root / full_path).resolve()
    if dist_root in target.parents and target.is_file():
        return FileResponse(target, headers={"Cache-Control": NO_CACHE})

    return _index_response()