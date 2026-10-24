"""Детерминированный скоринг релевантности событий клиенту.
Не является «пересказом» — это фильтр для последующей LLM-интерпретации.
Устойчив к неполным данным: отсутствие полей → нулевой вклад."""
from typing import Any


def score_event(event: dict, client: dict, profile: dict) -> tuple[float, dict[str, Any]]:
    """Возвращает (score 0..1, breakdown с совпавшими признаками)."""
    entities = [str(e).lower() for e in event.get("entities", []) or []]
    regions  = [str(r).lower() for r in event.get("regions", []) or []]
    industries = [str(i).lower() for i in event.get("industries", []) or []]
    title = (event.get("title") or "").lower()
    body  = (event.get("body") or "").lower()

    cps = profile.get("counterparties", []) or []
    profile_regions = [str(r).lower() for r in profile.get("regions", []) or []]
    keywords = [str(k).lower() for k in profile.get("keywords", []) or []]
    client_industry = (client.get("industry") or "").lower()

    breakdown = {"counterparties": [], "regions": [], "industry": None, "keywords": [], "magnitude": 0.0}

    score = 0.0
    # 1) Контрагенты — максимальный вес (0.4 на каждое совпадение, cap 0.8)
    cp_hits = 0
    for cp in cps:
        if cp.get("name", "").lower() in entities:
            breakdown["counterparties"].append(cp.get("name"))
            cp_hits += 1
    score += min(cp_hits * 0.4, 0.8)

    # 2) Отрасль — 0.25
    if client_industry and client_industry in industries:
        breakdown["industry"] = client.get("industry")
        score += 0.25

    # 3) Регионы — 0.15 суммарно
    region_hits = [r for r in event.get("regions", []) or [] if str(r).lower() in profile_regions]
    if region_hits:
        breakdown["regions"] = region_hits
        score += min(0.15 * len(region_hits), 0.15)

    # 4) Ключевые слова — до 0.1
    kw_hits = [k for k in keywords if k in title or k in body]
    if kw_hits:
        breakdown["keywords"] = kw_hits
        score += min(0.05 * len(kw_hits), 0.1)

    # 5) Magnitude — до 0.2
    mag = float(event.get("magnitude", 0.5) or 0.0)
    breakdown["magnitude"] = mag
    score += mag * 0.2

    return round(min(score, 1.0), 3), breakdown