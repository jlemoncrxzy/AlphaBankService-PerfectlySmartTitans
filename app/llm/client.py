"""LLM-клиент."""
import json
import re
from dataclasses import dataclass
from typing import Any
import httpx
from ..config import settings

@dataclass
class LLMResult:
    payload: dict[str, Any]
    provider: str
    model: str
    fallback: bool = False
    error: str = ""

SYSTEM_PROMPT = (
    "Ты — AI-аналитик Альфа-Банка для руководителей крупного бизнеса. "
    "Твоя задача — не пересказать новость или PDF-отчет, а объяснить, как событие влияет "
    "именно на этого клиента (риски/возможности), с опорой на его профиль. "
    "ОБЯЗАТЕЛЬНО используй предоставленный контекст из PDF-отчетов, если он относится к делу. "
    "Отвечай строго валидным JSON без markdown-обёрток."
)

USER_TEMPLATE = """Профиль клиента:
{profile}

Событие ({source_type}):
title: {title}
body: {body}
entities: {entities}
industries: {industries}
regions: {regions}

Дополнительный контекст из аналитических PDF-отчетов Альфа-Банка (RAG):
{rag}

ИНСТРУКЦИЯ: Объясни влияние события на клиента. Свяжи факты из новости или PDF с профилем клиента. 
ВАЖНО: Ты ОБЯЗАН найти хотя бы один риск или возможность. Отвечать "neutral" запрещено, если событие хоть как-то связано с отраслью, регионом или контрагентом клиента (даже если это макроэкономический отчет). Если прямых совпадений нет, оцени косвенное влияние на бизнес.

Верни JSON:
{{
  "kind": "risk" | "opportunity",
  "headline": "краткая персонализированная формулировка",
  "mechanism": "почему это важно ИМЕННО для этого клиента (со ссылкой на данные из PDF, если они есть)",
  "affected_business_lines": ["..."],
  "confidence": 0.0-1.0,
  "recommended_actions": ["..."],
  "caveats": ["..."]
}}
"""

class LLMClient:
    def __init__(self):
        self.provider = settings.llm_provider
        self.model_name = settings.llm_model
        self._heuristic = HeuristicInterpreter()

    def interpret_event(
        self, client_ctx: dict, profile: dict, event: dict,
        source_type: str, rag_snippets: list[str],
    ) -> LLMResult:
        if self.provider == "deepseek" and settings.deepseek_api_key:
            try:
                payload = self._call_deepseek(client_ctx, profile, event, source_type, rag_snippets)
                return LLMResult(payload=payload, provider="deepseek", model=self.model_name, fallback=False)
            except Exception as e:
                payload = self._heuristic.interpret(client_ctx, profile, event, source_type, rag_snippets)
                return LLMResult(payload=payload, provider="heuristic", model="heuristic-v1", fallback=True, error=str(e))
        
        payload = self._heuristic.interpret(client_ctx, profile, event, source_type, rag_snippets)
        return LLMResult(payload=payload, provider="heuristic", model="heuristic-v1", fallback=False)

    def _call_deepseek(self, client_ctx, profile, event, source_type, rag_snippets) -> dict:
        user = USER_TEMPLATE.format(
            profile=json.dumps({"industry": client_ctx.get("industry"), "profile": profile}, ensure_ascii=False),
            source_type=source_type,
            title=event.get("title", ""),
            body=event.get("body", ""),
            entities=json.dumps(event.get("entities", []), ensure_ascii=False),
            industries=json.dumps(event.get("industries", []), ensure_ascii=False),
            regions=json.dumps(event.get("regions", []), ensure_ascii=False),
            rag="\n".join(f"- {s}" for s in rag_snippets[:3]) or "нет",
        )
        
        # Исправленный URL (без /v1 в конце, если он уже есть в базовом)
        url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        
        with httpx.Client(timeout=settings.tool_timeout_seconds * 3) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        return _parse_json(content)

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)

class HeuristicInterpreter:
    def interpret(self, client_ctx: dict, profile: dict, event: dict, source_type: str, rag_snippets: list[str] = None) -> dict:
        title = event.get("title", "") or "Событие без заголовка"
        body = event.get("body", "") or ""
        entities = [str(e).lower() for e in event.get("entities", []) or []]
        regions  = [str(r).lower() for r in event.get("regions", []) or []]
        industries = [str(i).lower() for i in event.get("industries", []) or []]

        profile_cps = profile.get("counterparties", []) or []
        profile_regions = [str(r).lower() for r in profile.get("regions", []) or []]
        profile_products = profile.get("products", []) or []
        client_industry = (client_ctx.get("industry") or "").lower()

        matched_cps = [cp for cp in profile_cps if cp.get("name", "").lower() in entities]
        matched_regions = [r for r in event.get("regions", []) or [] if str(r).lower() in profile_regions]
        industry_match = client_industry and client_industry in industries

        mechanism_parts = []
        affected = []
        kind = "risk"
        confidence = 0.4

        for cp in matched_cps:
            role = cp.get("role", "")
            name = cp.get("name", "")
            share = cp.get("share", "")
            if role == "supplier":
                kind = "risk"
                mechanism_parts.append(f"«{name}» — ваш поставщик (доля {share}). Событие влияет на себестоимость.")
                affected.append("Закупки")
            elif role == "customer":
                kind = "risk"
                mechanism_parts.append(f"«{name}» — ваш клиент (доля {share}). Изменение спроса влияет на выручку.")
                affected.append("Выручка")
            elif role == "competitor":
                kind = "opportunity"
                mechanism_parts.append(f"«{name}» — конкурент. Его проблемы открывают возможности.")
                affected.append("Доля рынка")
            confidence = min(0.95, confidence + 0.2)

        if matched_regions:
            mechanism_parts.append(f"Событие затрагивает ваш регион: {', '.join(matched_regions)}.")
            affected.append("Регион")
            confidence = min(0.95, confidence + 0.1)

        if industry_match:
            mechanism_parts.append(f"Событие относится к вашей отрасли «{client_ctx.get('industry')}».")
            affected.append("Отрасль")
            confidence = min(0.95, confidence + 0.15)
            
            if source_type == "analytic":
                text_lower = (title + " " + body).lower()
                if any(w in text_lower for w in ["рост", "увеличение", "возможности", "поддержка", "субсиди", "льгот"]):
                    kind = "opportunity"
                if any(w in text_lower for w in ["падение", "снижение", "риск", "кризис", "проблем", "пошлин"]):
                    kind = "risk"

        if rag_snippets:
            mechanism_parts.append("В анализе учтены данные из отчетов Альфа-Банка.")
            affected.append("Аналитика")
            confidence = min(0.95, confidence + 0.1)

        if not mechanism_parts:
            mechanism_parts.append("Оценивается общее влияние на бизнес-среду. Рекомендован мониторинг.")
            affected.append("Общий мониторинг")
            confidence = 0.3

        return {
            "kind": kind,
            "headline": title,
            "mechanism": " ".join(mechanism_parts),
            "affected_business_lines": affected or ["Общий мониторинг"],
            "confidence": round(confidence, 2),
            "recommended_actions": ["Проверить контрагентов", "Оценить бюджет"] if kind == "risk" else ["Оценить новые возможности"],
            "caveats": ["Сформировано автоматически (offline)."],
        }