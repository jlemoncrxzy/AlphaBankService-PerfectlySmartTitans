"""Правила оценки рисков/возможностей и локальный fallback для LLM."""
from .document_overrides import get_document_override
from .text import clean_list, clean_text, headline_from_text, is_filename, summarize_text

PRODUCT_KNOWLEDGE = {
    "РКО": "расчётно-кассовое обслуживание: счета, платежи, эквайринг и контроль поступлений.",
    "Кредиты": "кредитные линии и оборотное финансирование для пополнения оборотных средств.",
    "Лизинг": "финансирование покупки техники и оборудования с графиком платежей.",
    "Гарантии": "банковские гарантии для контрактов, тендеров и обязательств перед контрагентами.",
    "Депозиты": "размещение свободных средств для получения процентного дохода.",
    "Зарплатный проект": "выплата зарплаты сотрудникам через банк и связанные сервисы.",
}

DIRECT_INDUSTRY_ALIASES = {
    "Металлургия": ("металл", "стал", "прокат", "труб", "арматур"),
    "Добыча": ("добыч", "полезн", "нефт", "газ", "уголь", "золот"),
    "Финансы": ("финанс", "банк", "страхов", "кредит", "лизинг"),
    "Инвестиции": ("инвест", "финанс"),
    "Ритейл": ("торговл", "розничн", "оптов", "магазин", "ресторан", "общепит"),
}

METALS_CONSUMER_MARKERS = (
    "строит", "монтаж", "машиностро", "перевозк", "транспорт", "производств", "обработк",
)
RETAIL_MARKERS = ("торговл", "розничн", "оптов", "магазин", "ресторан", "общепит")

RISK_MARKERS = {
    "риск", "снижен", "паден", "сокращ", "дефицит", "кризис", "санкц", "пошлин",
    "инфляц", "удорожан", "ограничен", "задержк", "проблем", "негатив", "ухудш",
    "потер", "штраф", "атак", "сбой", "охлажд", "жестк", "давлен",
}
OPPORTUNITY_MARKERS = {
    "возможност", "поддержк", "субсиди", "льгот", "восстановлен", "расширен",
    "инвестиц", "прибыл", "экспорт", "коридор", "импортозамещ", "господдержк",
    "ралли", "сильн", "рост",
}
STRONG_RISK = {"кризис", "санкц", "негатив", "дефицит", "атак", "сбой", "риск"}
STRONG_OPPORTUNITY = {"возможност", "субсиди", "господдержк", "импортозамещ", "ралли", "прибыл"}


def kind_label_ru(kind: str | None) -> str:
    return {
        "risk": "риск",
        "opportunity": "возможность",
        "neutral": "нейтральное событие",
    }.get(kind or "neutral", "событие")


def _matches(text: str, markers) -> bool:
    return any(marker in text for marker in markers)


def _has_product(products: list[str], marker: str) -> bool:
    marker = marker.lower()
    return any(marker in product.lower() for product in products)


def _direct_industries(client_industry: str, document_industries: list[str]) -> list[str]:
    industry = (client_industry or "").lower()
    matched = []
    for document_industry in document_industries:
        aliases = DIRECT_INDUSTRY_ALIASES.get(document_industry, ())
        if document_industry.lower() in industry or any(alias in industry for alias in aliases):
            matched.append(document_industry)
    return matched


def _rate_direction(text: str) -> str | None:
    if "ставк" not in text and "цб" not in text:
        return None

    high_phrases = (
        "без изменения",
        "взял паузу",
        "взяли паузу",
        "не рассматривал",
        "риторика стала жестче",
        "риторика стала жёстче",
        "жесткая ставка",
        "жёсткая ставка",
    )
    down_phrases = (
        "цикл снижения",
        "снижение ставки",
        "снижать ставку",
        "смягчение денежно-кредитной",
    )
    if _matches(text, high_phrases):
        return "high"
    if _matches(text, down_phrases):
        return "down"
    return None


def _keyword_kind(text: str) -> tuple[str, float]:
    risk_score = sum(
        text.count(marker) * (2 if marker in STRONG_RISK else 1)
        for marker in RISK_MARKERS
    )
    opportunity_score = sum(
        text.count(marker) * (2 if marker in STRONG_OPPORTUNITY else 1)
        for marker in OPPORTUNITY_MARKERS
    )
    if opportunity_score >= risk_score + 2:
        return "opportunity", opportunity_score - risk_score
    if risk_score >= opportunity_score + 2:
        return "risk", risk_score - opportunity_score
    return "neutral", abs(risk_score - opportunity_score)


def _client_matches(client_ctx: dict, event: dict) -> tuple[list, list]:
    entities = [str(entity).lower() for entity in event.get("entities") or []]
    counterparties = [
        counterparty
        for counterparty in client_ctx.get("counterparties") or []
        if str(counterparty.get("name", "")).lower() in entities
    ]
    profile_regions = [str(region).lower() for region in client_ctx.get("regions") or []]
    event_regions = [str(region) for region in event.get("regions") or []]
    matched_regions = [
        region for region in event_regions
        if region.lower() in profile_regions and region.lower() != "россия"
    ]
    return counterparties, matched_regions


def _build_actions(kind: str, products: list[str]) -> list[str]:
    actions: list[str] = []

    if kind == "risk":
        if _has_product(products, "кредит"):
            actions.append("Проверить доступный лимит по кредитной линии")
        if _has_product(products, "лизинг"):
            actions.append("Проверить график лизинговых платежей")
        if _has_product(products, "гарант"):
            actions.append("Проверить лимит по банковским гарантиям")
        actions.append("Пересмотреть бюджет и график платежей")
        actions.append("Обсудить сценарий с экспертом Альфа-Банка")
        if _has_product(products, "депозит"):
            actions.append("Пересмотреть размещение свободных средств")
    elif kind == "opportunity":
        if _has_product(products, "кредит"):
            actions.append("Запросить расчёт кредитной линии под новую возможность")
        if _has_product(products, "лизинг"):
            actions.append("Запросить расчёт лизинга оборудования")
        if _has_product(products, "депозит"):
            actions.append("Оценить размещение свободных средств")
        actions.append("Оценить объём и сроки использования возможности")
        actions.append("Согласовать условия с контрагентами")
    else:
        actions.append("Продолжить мониторинг документа")
        actions.append("Проверить профиль компании при следующем обновлении")

    return clean_list(actions, limit=5)


def _build_cta(kind: str, products: list[str]) -> str:
    if kind == "risk":
        return "Проверить лимит" if _has_product(products, "кредит") else "Пересмотреть график"
    if kind == "opportunity":
        return "Оценить возможность"
    return "Мониторинг"


def _build_mechanism(
    kind: str,
    client_ctx: dict,
    direct_industries: list[str],
    matched_counterparties: list,
    matched_regions: list[str],
    is_metals_consumer: bool,
    is_retail: bool,
    is_macro: bool,
    is_finance: bool,
    rate: str | None,
    products: list[str],
) -> str:
    industry = clean_text(client_ctx.get("industry"))
    parts: list[str] = []

    if is_macro or is_finance:
        parts.append("Документ затрагивает макроэкономические и финансовые условия.")
    elif direct_industries:
        parts.append(f"Документ напрямую относится к вашей отрасли «{industry}».")
    elif is_metals_consumer:
        parts.append(f"Для вашей отрасли «{industry}» это влияет на закупки и себестоимость.")
    elif is_retail:
        parts.append(f"Документ влияет на потребительский спрос в отрасли «{industry}».")
    else:
        parts.append("Прямых пересечений с профилем клиента в документе нет.")

    has_credit = _has_product(products, "кредит") or _has_product(products, "лизинг")
    has_deposit = _has_product(products, "депозит")

    if rate == "down":
        if has_credit:
            parts.append("Снижение ставки удешевляет заёмное финансирование.")
        else:
            parts.append("Снижение ставки улучшает общие условия финансирования.")
    elif rate == "high":
        if has_credit:
            parts.append("Сохранение жёсткой ставки удорожает обслуживание долга и новых кредитов.")
        elif has_deposit:
            parts.append("Жёсткая ставка поддерживает доходность размещения свободных средств.")
        else:
            parts.append("Жёсткая ставка ограничивает доступность и стоимость финансирования.")

    if matched_counterparties:
        names = ", ".join(f"«{item.get('name')}»" for item in matched_counterparties[:2])
        parts.append(f"Среди контрагентов в документе упомянуты: {names}.")

    if matched_regions:
        parts.append(f"Затронуты регионы вашего присутствия: {', '.join(matched_regions[:2])}.")

    if kind == "risk":
        parts.append("Основной риск — давление на маржу, ликвидность или график платежей.")
    elif kind == "opportunity":
        parts.append("Основная возможность — улучшить условия закупок, финансирования или нарастить выручку.")
    else:
        parts.append("Выраженного влияния на компанию не выявлено, событие остаётся в мониторинге.")

    return " ".join(parts)


class HeuristicInterpreter:
    """Детерминированная интерпретация, когда DeepSeek недоступен."""

    def interpret(
        self,
        client_ctx: dict,
        profile: dict,
        event: dict,
        source_type: str,
        rag_snippets: list[str] | None = None,
    ) -> dict:
        override = get_document_override(event.get("title"))
        title = clean_text(event.get("title"))
        body = clean_text(event.get("body"))
        text = f"{title} {body}".lower()
        document_industries = [str(item) for item in event.get("industries") or []]

        client_industry = clean_text(client_ctx.get("industry"))
        products = [clean_text(product) for product in client_ctx.get("products") or []]

        direct_industries = _direct_industries(client_industry, document_industries)
        matched_counterparties, matched_regions = _client_matches(client_ctx, event)

        is_metals = (
            any(item in document_industries for item in ("Металлургия", "Добыча"))
            or _matches(text, ("сталь", "сталей", "металл", "золот", "прокат", "труб"))
        )
        is_gold = "золот" in text or "gold" in title.lower()
        if document_industries:
            is_macro = "Макро" in document_industries
            is_finance = any(
                item in document_industries for item in ("Финансы", "Инвестиции")
            )
        else:
            is_macro = _matches(text, ("ввп", "макроэкономи", "инфляц", "потреблен", "ключевая ставка"))
            is_finance = _matches(text, ("офз", "облигац", "доходност", "ключевая ставка"))
        is_retail = "Ритейл" in document_industries or _matches(text, ("розничн", "потреблен"))
        rate_focus = (
            ("ставк" in text or "цб" in text)
            and _matches(text, ("цб", "ключев", "снижен", "пауз", "риторик"))
        )
        rate = _rate_direction(text) if rate_focus and (is_macro or is_finance) else None

        base_kind = override.get("kind_hint") if override else None
        if base_kind not in {"risk", "opportunity", "neutral"}:
            base_kind, _ = _keyword_kind(text)

        kind = base_kind
        has_credit = _has_product(products, "кредит") or _has_product(products, "лизинг")
        has_deposit = _has_product(products, "депозит")

        if rate == "down":
            kind = "risk" if has_deposit and not has_credit else "opportunity"
        elif rate == "high":
            kind = "opportunity" if has_deposit and not has_credit else "risk"

        is_metals_consumer = is_metals and bool(
            _matches(client_industry.lower(), METALS_CONSUMER_MARKERS)
        )
        is_retail_client = bool(_matches(client_industry.lower(), RETAIL_MARKERS))

        if is_gold:
            # Обзор рынка золота релевантен только добытчикам и металлургам,
            # а не всем потребителям металла (строительству, перевозкам).
            kind = base_kind if direct_industries else "neutral"
        elif is_metals and rate is None:
            if direct_industries:
                kind = base_kind
            elif is_metals_consumer:
                kind = "risk" if base_kind in {"opportunity", "risk"} else "neutral"
            else:
                kind = "neutral"

        if is_retail and not is_macro and not direct_industries and not is_retail_client:
            kind = "neutral"

        if not direct_industries and not is_macro and not is_finance and not is_metals and not matched_counterparties:
            kind = "neutral"

        confidence = 0.4
        if direct_industries:
            confidence += 0.2
        if is_macro:
            confidence += 0.1
        if is_finance:
            confidence += 0.05
        if matched_counterparties:
            confidence += 0.2
        if matched_regions:
            confidence += 0.1
        if rate:
            confidence += 0.05
        if override:
            confidence += 0.05
        confidence = round(min(0.9, confidence), 2)
        if kind == "neutral":
            confidence = min(confidence, 0.6)

        summary = (override or {}).get("summary") or summarize_text(body or title)
        details = (
            (override or {}).get("details")
            or (summary if override else summarize_text(body, max_sentences=4, max_chars=700))
            or summary
        )
        headline = (override or {}).get("headline")
        if not headline:
            headline = clean_text(title) if not is_filename(title) else headline_from_text(body, title)

        mechanism = _build_mechanism(
            kind=kind,
            client_ctx=client_ctx,
            direct_industries=direct_industries,
            matched_counterparties=matched_counterparties,
            matched_regions=matched_regions,
            is_metals_consumer=is_metals_consumer and is_metals,
            is_retail=is_retail and is_retail_client,
            is_macro=is_macro,
            is_finance=is_finance,
            rate=rate,
            products=products,
        )

        affected = []
        if kind == "risk":
            affected.extend(["Маржа", "Ликвидность"])
        elif kind == "opportunity":
            affected.extend(["Выручка", "Финансирование"])
        else:
            affected.append("Мониторинг")
        if direct_industries:
            affected.append(direct_industries[0])
        elif is_macro:
            affected.append("Макро")
        elif is_finance:
            affected.append("Финансы")
        affected.extend(products[:2])

        caveats = ["Оценка автоматическая: основана на тексте документа и профиле клиента."]
        if is_finance:
            caveats.append("Не является индивидуальной инвестиционной рекомендацией.")

        return {
            "kind": kind,
            "confidence": confidence,
            "headline": headline,
            "summary": summary,
            "details": details,
            "mechanism": mechanism,
            "affected_business_lines": clean_list(affected, limit=4),
            "recommended_actions": _build_actions(kind, products),
            "cta": _build_cta(kind, products),
            "caveats": clean_list(caveats, limit=2),
        }


def build_chat_answer(
    question: str,
    client_ctx: dict,
    insight: dict,
    siblings: list[dict],
) -> str:
    """Структурированная сводка, когда DeepSeek недоступен."""
    query = (question or "").lower()
    name = client_ctx.get("name") or "клиент"
    industry = client_ctx.get("industry") or "отрасль не указана"
    products = client_ctx.get("products") or []

    asks_actions = _matches(query, ("что делать", "рекоменд", "действ", "шаг"))
    asks_risks = _matches(query, ("риск", "угроз", "опасн"))
    asks_opportunities = _matches(query, ("возможност", "шанс", "рост"))
    asks_products = _matches(query, ("рко", "кредит", "лизинг", "гарант", "депозит", "зарплат", "продукт", "услуг", "банк", "систем"))

    blocks: list[str] = [f"Компания: {name} · {industry}."]

    if asks_products:
        if products:
            product_lines = [
                "Подключённые продукты: " + ", ".join(products) + ".",
                *[
                    f"• {product}: {PRODUCT_KNOWLEDGE[product]}"
                    for product in products[:4]
                    if product in PRODUCT_KNOWLEDGE
                ],
            ]
            blocks.append("\n".join(product_lines))
        else:
            blocks.append("В профиле компании не указаны подключённые продукты.")

    risks = [item for item in siblings if item.get("type") == "risk"]
    opportunities = [item for item in siblings if item.get("type") == "opportunity"]

    focus = insight
    if asks_risks and risks:
        focus = risks[0]
    elif asks_opportunities and opportunities:
        focus = opportunities[0]

    if asks_products and not (asks_actions or asks_risks or asks_opportunities):
        blocks.append(
            f"По текущей новости: {insight.get('summary') or 'нет описания.'}"
        )
        return "\n\n".join(blocks)

    if asks_actions and (focus.get("actions") or []):
        blocks.append(f"Документ: «{focus.get('title', 'Без названия')}».")
        blocks.append(
            "Что можно сделать:\n"
            + "\n".join(
                f"{index}. {action}"
                for index, action in enumerate(focus["actions"], start=1)
            )
        )
        return "\n\n".join(blocks)

    if asks_risks:
        if risks:
            blocks.append(
                "Риски в текущей ленте:\n"
                + "\n".join(
                    f"• {item['title']} — {item['summary']}" for item in risks[:4]
                )
            )
        else:
            blocks.append("В текущей ленте нет выраженных рисков.")
    elif asks_opportunities:
        if opportunities:
            blocks.append(
                "Возможности в текущей ленте:\n"
                + "\n".join(
                    f"• {item['title']} — {item['summary']}"
                    for item in opportunities[:4]
                )
            )
        else:
            blocks.append("В текущей ленте нет выраженных возможностей.")
    else:
        blocks.append(f"Документ: «{insight.get('title', 'Без названия')}».")
        blocks.append(f"Что произошло: {insight.get('summary') or 'Нет описания.'}")
        blocks.append(
            f"Оценка: {kind_label_ru(insight.get('type'))}"
            + (
                f", уверенность {insight['confidence']}%."
                if insight.get("confidence") is not None
                else "."
            )
        )
        blocks.append(f"Почему важно: {insight.get('impact') or 'Нет данных.'}")

    actions = focus.get("actions") or []
    if actions:
        blocks.append(
            "Что можно сделать:\n"
            + "\n".join(
                f"{index}. {action}"
                for index, action in enumerate(actions, start=1)
            )
        )

    caveats = focus.get("caveats") or insight.get("caveats") or []
    if caveats:
        blocks.append("Ограничения: " + "; ".join(caveats) + ".")

    others = [item for item in siblings if item.get("id") != insight.get("id")]
    if others and not asks_risks and not asks_opportunities:
        blocks.append(
            "Другие события в ленте:\n"
            + "\n".join(
                f"• {item['title']} — {kind_label_ru(item.get('type'))}"
                for item in others[:4]
            )
        )

    return "\n\n".join(blocks)
