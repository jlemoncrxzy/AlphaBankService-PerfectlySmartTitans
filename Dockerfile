# syntax=docker/dockerfile:1

# ============================================================================
#  Stage 1 — сборка React-фронтенда (Vite)
# ============================================================================
FROM node:22-alpine AS frontend
WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ============================================================================
#  Stage 2 — рантайм FastAPI + собранный UI
# ============================================================================
FROM python:3.13-slim AS runtime

# Тяжёлые опциональные штуки выключены по умолчанию:
#   INSTALL_DEV_DEPS=true     → pdfplumber / PyMuPDF / easyocr(+torch ~3 ГБ) для PDF-ингеста
#   INSTALL_LIBREOFFICE=true  → конвертация legacy .doc шаблонов отчёта (soffice)
ARG INSTALL_DEV_DEPS=false
ARG INSTALL_LIBREOFFICE=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    DATABASE_URL=sqlite:////app/data/app.db

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && if [ "$INSTALL_LIBREOFFICE" = "true" ]; then \
        apt-get install -y --no-install-recommends libreoffice-writer; \
    fi \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && if [ "$INSTALL_DEV_DEPS" = "true" ]; then pip install -r requirements-dev.txt; fi

COPY app ./app
# Из data/ в образ попадает только пример шаблона (см. .dockerignore):
# сама БД, CSV и PDF монтируются томом на /app/data.
COPY data ./data

# Собранный UI берём из первой стадии: Node в рантайм-образе не нужен.
COPY --from=frontend /build/frontend/dist ./frontend/dist

RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /app/data \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

# sh -c нужен, чтобы подставить $PORT (Render/Railway задают его сами).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
