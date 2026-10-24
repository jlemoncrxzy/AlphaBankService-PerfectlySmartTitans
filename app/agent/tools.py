"""Инструменты агента. Каждый вызов журналируется в ToolLog (whitelist + результат).
Это и есть «контроль и журналирование обращений к инструментам» из ТЗ.
"""
from typing import Any
from sqlalchemy.orm import Session
# Обратите внимание: добавлен импорт DocumentChunk для работы с нарезанными PDF
from ..models import Client, ClientProfile, NewsItem, BankAnalytic, ToolLog, DocumentChunk

# Whitelist инструментов — защита от потенциально небезопасных действий.
ALLOWED_TOOLS = {
    "get_client_profile",
    "search_news",
    "search_bank_analytics",
    "search_rag",
    "llm_interpret",
}

# Лимиты на параметры — защита от исчерпания ресурсов / инъекций.
MAX_QUERY_LEN = 200
MAX_TOP_K = 20


def _sanitize(obj: Any) -> Any:
    """Убираем потенциально чувствительные/огромные поля из журнала."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()
                if k.lower() not in {"password", "token", "secret"}}
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj[:20]]
    if isinstance(obj, str):
        return obj[:500]
    return obj


def _log(db: Session, run_id: int | None, user_id: int | None, tool: str,
         params: dict, allowed: bool, summary: str = "", reason: str = "") -> None:
    db.add(ToolLog(
        run_id=run_id, user_id=user_id, tool=tool,
        params=_sanitize(params), allowed=allowed,
        result_summary=summary[:500], reason=reason[:255],
    ))
    db.commit()


def _guard(tool: str, db: Session, run_id: int | None, user_id: int | None, params: dict) -> bool:
    if tool not in ALLOWED_TOOLS:
        _log(db, run_id, user_id, tool, params, allowed=False, reason="tool_not_allowed")
        return False
    return True


# ---------------- инструменты ----------------

def get_client_profile(db: Session, run_id: int, user_id: int, client_id: int) -> dict | None:
    if not _guard("get_client_profile", db, run_id, user_id, {"client_id": client_id}):
        return None
    client = db.get(Client, client_id)
    if not client:
        _log(db, run_id, user_id, "get_client_profile", {"client_id": client_id},
             allowed=True, summary="not_found")
        return None
    p = client.profile
    result = {
        "id": client.id, "name": client.name, "industry": client.industry,
        "scale_revenue_rub": client.scale_revenue_rub,
        "scale_employees": client.scale_employees,
        "description": client.description,
        "products": (p.products if p else []) or [],
        "counterparties": (p.counterparties if p else []) or [],
        "regions": (p.regions if p else []) or [],
        "keywords": (p.keywords if p else []) or [],
        "risk_notes": (p.risk_notes if p else "") or "",
    }
    _log(db, run_id, user_id, "get_client_profile", {"client_id": client_id},
         allowed=True, summary=f"loaded profile for {client.name}")
    return result


def search_news(db: Session, run_id: int, user_id: int, queries: list[str],
                limit: int = 10) -> list[dict]:
    limit = min(max(limit, 1), MAX_TOP_K)
    params = {"queries": [q[:MAX_QUERY_LEN] for q in queries], "limit": limit}
    if not _guard("search_news", db, run_id, user_id, params):
        return []

    q = db.query(NewsItem)
    terms = [t.lower() for t in queries if t]
    items = []
    for n in q.order_by(NewsItem.published_at.desc()).limit(200).all():
        text = f"{n.title} {n.body}".lower()
        if not terms or any(t in text for t in terms):
            items.append(n)
        if len(items) >= limit:
            break
    if not items:
        items = q.order_by(NewsItem.published_at.desc()).limit(limit).all()

    _log(db, run_id, user_id, "search_news", params, allowed=True,
         summary=f"found {len(items)} news")
    return [_row_to_dict(n) for n in items]


def search_bank_analytics(db: Session, run_id: int, user_id: int, queries: list[str],
                          limit: int = 5) -> list[dict]:
    limit = min(max(limit, 1), MAX_TOP_K)
    params = {"queries": [q[:MAX_QUERY_LEN] for q in queries], "limit": limit}
    if not _guard("search_bank_analytics", db, run_id, user_id, params):
        return []

    q = db.query(BankAnalytic)
    terms = [t.lower() for t in queries if t]
    items = []
    for a in q.order_by(BankAnalytic.published_at.desc()).limit(200).all():
        text = f"{a.title} {a.body}".lower()
        if not terms or any(t in text for t in terms):
            items.append(a)
        if len(items) >= limit:
            break
    if not items:
        items = q.order_by(BankAnalytic.published_at.desc()).limit(limit).all()

    _log(db, run_id, user_id, "search_bank_analytics", params, allowed=True,
         summary=f"found {len(items)} analytics")
    return [_row_to_dict(a) for a in items]


def search_rag(db: Session, run_id: int, user_id: int, query: str,
               top_k: int = 3) -> list[str]:
    """RAG-поиск по нарезанным PDF-файлам (таблица DocumentChunk).
    Ищет совпадения по словам из запроса и отрасли."""
    top_k = min(max(top_k, 1), MAX_TOP_K)
    params = {"query": query[:MAX_QUERY_LEN], "top_k": top_k}
    if not _guard("search_rag", db, run_id, user_id, params):
        return []

    # Извлекаем ключевые слова (длиной больше 3 символов)
    terms = [t for t in query.lower().split() if len(t) > 3]
    if not terms:
        terms = [query.lower()]

    # Простой, но эффективный скоринг: чем больше слов из запроса встречается в чанке — тем выше релевантность
    chunks = db.query(DocumentChunk).all()
    scored_chunks = []
    
    for chunk in chunks:
        text_lower = chunk.text.lower()
        score = sum(1 for term in terms if term in text_lower)
        # Бонус за совпадение отрасли
        if any(str(ind).lower() in text_lower for ind in (chunk.industries or [])):
            score += 2
            
        if score > 0:
            scored_chunks.append((score, chunk.text))

    # Сортируем по убыванию релевантности и берем топ-K
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    snippets = [text for _, text in scored_chunks[:top_k]]

    # Если ничего не нашли, отдаем случайные 2 куска из аналитики (чтобы LLM было от чего отталкиваться)
    if not snippets and chunks:
        snippets = [c.text for c in chunks[:2]]

    _log(db, run_id, user_id, "search_rag", params, allowed=True,
         summary=f"returned {len(snippets)} PDF chunks")
    return snippets


def _row_to_dict(row) -> dict:
    if isinstance(row, NewsItem):
        return {
            "id": row.id, "title": row.title, "body": row.body, "source": row.source,
            "published_at": row.published_at.isoformat(), "entities": row.entities or [],
            "industries": row.industries or [], "regions": row.regions or [],
            "magnitude": row.magnitude, "url": row.url, "_type": "news",
        }
    return {
        "id": row.id, "title": row.title, "body": row.body, "category": row.category,
        "published_at": row.published_at.isoformat(), "entities": row.entities or [],
        "industries": row.industries or [], "regions": row.regions or [],
        "magnitude": row.magnitude, "_type": "analytic",
    }