"""API-адаптер React-дашборда.

Отдаёт только реальные данные из БД: профиль клиента, агрегаты платёжной
выгрузки и инсайты, сгенерированные пайплайном. Никаких захардкоженных
остатков и «красивых» коэффициентов.
"""
import re
from datetime import datetime
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..llm.client import LLMClient
from ..llm.text import clean_list, clean_text, is_filename, summarize_text
from ..metrics import load_payment_stats
from ..models import (
    AnalysisRun,
    BankAnalytic,
    Client,
    DocumentChunk,
    EventInsight,
    NewsItem,
)

router = APIRouter(prefix="/api", tags=["dashboard"])

UID_PATTERN = re.compile(r"(U_\d+)")
KINDS = {"risk", "opportunity", "neutral"}


@lru_cache(maxsize=1)
def _payment_stats() -> dict:
    """Кэш на процесс: JSON читается один раз, а не на каждый запрос."""
    return load_payment_stats()


class ChatRequest(BaseModel):
    question: str


def _uid(name: str | None) -> str | None:
    match = UID_PATTERN.search(name or "")
    return match.group(1) if match else None


def _iso_utc(value: datetime | None) -> str | None:
    return f"{value.isoformat()}Z" if value else None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value: float | None) -> str | None:
    if value is None or value <= 0:
        return None
    if value >= 1e9:
        return f"{value / 1e9:.1f} млрд ₽".replace(".", ",")
    if value >= 1e6:
        return f"{value / 1e6:.1f} млн ₽".replace(".", ",")
    if value >= 1e3:
        return f"{value / 1e3:.1f} тыс ₽".replace(".", ",")
    return f"{value:.0f} ₽"


def _date_label(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y, %H:%M") if value else "—"


def _excerpt(text: str | None, limit: int = 260) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    cut = normalized[:limit].rsplit(" ", 1)[0]
    return f"{cut.rstrip('.,;:')}…"


def _pretty_title(title: str) -> str:
    cleaned = (title or "").strip()
    if cleaned.lower().endswith(".pdf"):
        cleaned = cleaned[:-4].replace("_", " ").strip()
    return cleaned or "Событие без заголовка"


def _provider_info(insight: EventInsight) -> tuple[str, str, bool]:
    for source in insight.sources or []:
        provider = source.get("provider")
        if provider:
            return provider, source.get("model") or "", bool(source.get("fallback"))
    return "Не указан", "", False


def format_client(
    client: Client,
    insights_count: int = 0,
    payment_stats: dict | None = None,
) -> dict:
    """Реальный профиль клиента без выдуманных остатков и депозитов."""
    profile = client.profile
    regions = list(profile.regions or []) if profile else []
    products = list(profile.products or []) if profile else []
    counterparties = list(profile.counterparties or []) if profile else []

    uid = _uid(client.name)
    stats = (payment_stats or {}).get(uid or "", {}) or {}
    revenue = _number(client.scale_revenue_rub)

    return {
        "id": str(client.id),
        "name": client.name,
        "industry": client.industry or "Не указана",
        "revenueRub": revenue,
        "revenue": _money(revenue),
        "regions": regions,
        "region": ", ".join(regions[:3]),
        "products": products,
        "counterpartiesCount": len(counterparties),
        "insightsCount": insights_count,
        "payments": {
            "hasData": bool(stats),
            "incomingRub": _number(stats.get("in")),
            "outgoingRub": _number(stats.get("out")),
            "incomingTransactions": int(stats.get("inTx") or 0),
            "outgoingTransactions": int(stats.get("outTx") or 0),
            "incomingCounterparties": int(stats.get("inCp") or 0),
            "outgoingCounterparties": int(stats.get("outCp") or 0),
        },
        "riskNotes": (profile.risk_notes if profile else "") or "",
    }


def format_insight(
    insight: EventInsight,
    source: NewsItem | BankAnalytic | None,
) -> dict:
    """Инсайт пайплайна + реальный текст источника."""
    # После переиндексации источников старые инсайты могут ссылаться на чужой
    # документ с тем же ID. В таком случае источник не подмешиваем.
    if source is not None:
        source_title = (getattr(source, "title", "") or "").strip().casefold()
        if source_title != (insight.title or "").strip().casefold():
            source = None

    impact = insight.impact or {}
    kind = impact.get("kind") if impact.get("kind") in KINDS else "neutral"

    confidence_value = _number(impact.get("confidence"))
    confidence = (
        round(max(0.0, min(1.0, confidence_value)) * 100)
        if confidence_value is not None
        else None
    )
    relevance_value = _number(insight.relevance_score) or 0.0
    relevance = round(max(0.0, min(1.0, relevance_value)) * 100)

    mechanism = clean_text(str(impact.get("mechanism") or ""))
    headline = clean_text(str(impact.get("headline") or ""))
    summary = clean_text(str(impact.get("summary") or ""))
    details = clean_text(str(impact.get("details") or ""))
    actions = clean_list(impact.get("recommended_actions"), limit=5)
    caveats = clean_list(impact.get("caveats"), limit=2)
    business_lines = clean_list(impact.get("affected_business_lines"), limit=4)
    cta = clean_text(str(impact.get("cta") or "")) or (actions[0] if actions else "Мониторинг")

    if headline and not is_filename(headline):
        title = headline
    else:
        title = _pretty_title(insight.title)
        if isinstance(source, BankAnalytic) and source.category:
            title = f"{source.category}: {title}"

    full_body = clean_text(getattr(source, "body", ""))
    if not summary:
        summary = summarize_text(full_body or insight.title, max_sentences=2, max_chars=240)
    facts = details or summary or mechanism or "Нет данных."
    opinion = mechanism or summary or "Недостаточно данных для оценки влияния."
    provider, model, fallback = _provider_info(insight)
    team = f"AI-аналитик · {model}" if model else "AI-аналитик"

    if kind == "risk":
        if confidence is None:
            type_label = "РИСК"
        elif confidence >= 70:
            type_label = "РИСК · Высокий"
        elif confidence >= 45:
            type_label = "РИСК · Средний"
        else:
            type_label = "РИСК · Низкий"
    elif kind == "opportunity":
        type_label = "ВОЗМОЖНОСТЬ"
    else:
        type_label = "СОБЫТИЕ"

    if isinstance(source, NewsItem):
        source_label = source.source or "Новость"
    elif isinstance(source, BankAnalytic):
        source_label = f"Альфа-Банк · {source.category}" if source.category else "Альфа-Банк"
    else:
        source_label = "База знаний банка"

    run = insight.run
    published = (run.finished_at or run.created_at) if run else None

    return {
        "id": str(insight.id),
        "type": kind,
        "typeLabel": type_label,
        "date": _date_label(published),
        "publishedAt": _iso_utc(published),
        "title": title,
        "summary": summary or mechanism or "Нет описания события.",
        "details": details or summary or mechanism or "Нет данных.",
        "tags": business_lines[:3],
        "industries": list(getattr(source, "industries", []) or []),
        "regions": list(getattr(source, "regions", []) or []),
        "bankOpinion": opinion,
        "bankSource": source_label,
        "bankTeam": team,
        "recommendation": cta,
        "cta": cta,
        "actions": actions,
        "source": source_label,
        "relevance": relevance,
        "confidence": confidence,
        "facts": facts,
        "impact": mechanism or "Нет данных.",
        "action": "; ".join(actions) if actions else "Нет рекомендаций.",
        "caveats": caveats,
        "sourceType": insight.source_type,
        "provider": provider,
        "model": model,
        "fallback": fallback,
    }


def _unique_insights(insights: list[EventInsight], limit: int = 10) -> list[EventInsight]:
    """Один и тот же документ мог попасть в несколько запусков — оставляем свежий."""
    unique: list[EventInsight] = []
    seen: set[tuple[str, int]] = set()
    for insight in insights:
        key = (insight.source_type, insight.source_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(insight)
        if len(unique) >= limit:
            break
    return unique


def _format_insights(db: Session, insights: list[EventInsight]) -> list[dict]:
    """Подтягивает источники и приводит инсайты к формату фронтенда."""
    news_ids = [item.source_id for item in insights if item.source_type == "news"]
    analytic_ids = [item.source_id for item in insights if item.source_type == "analytic"]

    news_map = (
        {item.id: item for item in db.query(NewsItem).filter(NewsItem.id.in_(news_ids)).all()}
        if news_ids else {}
    )
    analytic_map = (
        {item.id: item for item in db.query(BankAnalytic).filter(BankAnalytic.id.in_(analytic_ids)).all()}
        if analytic_ids else {}
    )

    formatted = []
    for insight in insights:
        source = (
            news_map.get(insight.source_id)
            if insight.source_type == "news"
            else analytic_map.get(insight.source_id)
        )
        formatted.append(format_insight(insight, source))
    return formatted


def _rag_snippets(db: Session, query: str, limit: int = 3) -> list[str]:
    """Простой поиск по нарезанным PDF для контекста чата."""
    terms = [
        term for term in re.findall(r"[а-яёa-z0-9]{4,}", query.lower())
        if term not in {"этого", "этой", "какие", "какой", "почему", "можно", "нужно"}
    ]
    if not terms:
        return []

    scored = []
    for chunk in db.query(DocumentChunk).limit(500).all():
        text = (chunk.text or "").lower()
        score = sum(text.count(term) for term in terms)
        if score:
            scored.append((score, chunk.text))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in scored[:limit]]


@router.get("/dashboard")
def get_dashboard(
    companyId: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    payment_stats = _payment_stats()

    client: Client | None = None
    if companyId:
        try:
            client = (
                db.query(Client)
                .options(joinedload(Client.profile))
                .filter(Client.id == int(companyId))
                .first()
            )
        except ValueError:
            client = None
        if client is None:
            raise HTTPException(404, "Клиент не найден")

    if client is None:
        latest_run = (
            db.query(AnalysisRun)
            .join(EventInsight, EventInsight.run_id == AnalysisRun.id)
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        if latest_run:
            client = (
                db.query(Client)
                .options(joinedload(Client.profile))
                .filter(Client.id == latest_run.client_id)
                .first()
            )
    if client is None:
        client = (
            db.query(Client)
            .options(joinedload(Client.profile))
            .order_by(Client.id)
            .first()
        )
    if client is None:
        raise HTTPException(404, "В базе нет клиентов")

    # Показываем только последний запуск клиента: так в ленту не попадают
    # устаревшие инсайты прошлых прогонов и дубли одного и того же документа.
    latest_run = (
        db.query(AnalysisRun)
        .join(EventInsight, EventInsight.run_id == AnalysisRun.id)
        .filter(AnalysisRun.client_id == client.id)
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
        .first()
    )
    insights = (
        db.query(EventInsight)
        .options(joinedload(EventInsight.run))
        .filter(EventInsight.run_id == latest_run.id)
        .order_by(EventInsight.id.desc())
        .all()
        if latest_run
        else []
    )
    selected = _unique_insights(insights, limit=10)

    news_items = _format_insights(db, selected)

    risks_count = sum(1 for item in news_items if item["type"] == "risk")
    opportunities_count = sum(1 for item in news_items if item["type"] == "opportunity")

    timestamps = [
        insight.run.finished_at or insight.run.created_at
        for insight in selected
        if insight.run and (insight.run.finished_at or insight.run.created_at)
    ]
    generated_at = max(timestamps) if timestamps else None

    companies_with_insights = (
        db.query(func.count(func.distinct(AnalysisRun.client_id)))
        .join(EventInsight, EventInsight.run_id == AnalysisRun.id)
        .scalar()
        or 0
    )

    company_rows = (
        db.query(Client, func.count(EventInsight.id).label("insights_count"))
        .options(joinedload(Client.profile))
        .join(AnalysisRun, AnalysisRun.client_id == Client.id)
        .join(EventInsight, EventInsight.run_id == AnalysisRun.id)
        .group_by(Client.id)
        .order_by(func.max(AnalysisRun.created_at).desc())
        .limit(30)
        .all()
    )
    if not any(row_client.id == client.id for row_client, _ in company_rows):
        company_rows.append((client, len(selected)))

    return {
        "company": format_client(client, len(selected), payment_stats),
        "companies": [
            format_client(row_client, int(count), payment_stats)
            for row_client, count in company_rows
        ],
        "news": news_items,
        "focusItems": [
            {"label": "Требуют внимания", "value": risks_count, "color": "red"},
            {"label": "Возможности роста", "value": opportunities_count, "color": "honey"},
            {"label": "Компаний в мониторинге", "value": int(companies_with_insights), "color": "dark"},
        ],
        "meta": {
            "generatedAt": _iso_utc(generated_at),
            "companiesWithInsights": int(companies_with_insights),
            "insightsTotal": len(selected),
            "risksCount": risks_count,
            "opportunitiesCount": opportunities_count,
            "paymentsAvailable": bool(payment_stats),
        },
    }


@router.post("/news/{news_id}/chat")
def chat_with_news(news_id: str, req: ChatRequest, db: Session = Depends(get_db)):
    try:
        insight_id = int(news_id)
    except ValueError:
        raise HTTPException(400, "Неверный ID новости") from None

    insight = db.get(EventInsight, insight_id)
    if insight is None:
        raise HTTPException(404, "Новость не найдена")

    client = db.get(Client, insight.run.client_id) if insight.run else None
    client_ctx = format_client(client, 0, _payment_stats()) if client else {
        "name": "клиент",
        "industry": "",
        "products": [],
        "regions": [],
        "revenueRub": None,
    }

    selected_item = _format_insights(db, [insight])[0]

    siblings: list[dict] = []
    if insight.run:
        run_insights = (
            db.query(EventInsight)
            .filter(EventInsight.run_id == insight.run_id)
            .order_by(EventInsight.id.desc())
            .all()
        )
        siblings = [
            item
            for item in _format_insights(db, _unique_insights(run_insights, limit=10))
            if item["id"] != selected_item["id"]
        ]

    rag = _rag_snippets(
        db,
        f"{req.question} {selected_item.get('title', '')} {client_ctx.get('industry', '')}",
    )

    result = LLMClient().answer_question(
        question=req.question,
        client_ctx=client_ctx,
        insight=selected_item,
        siblings=siblings,
        rag_snippets=rag,
    )

    return {
        "answer": result.answer,
        "provider": result.provider,
        "model": result.model,
        "fallback": result.fallback,
    }