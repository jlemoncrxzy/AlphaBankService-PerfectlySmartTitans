"""LLM-клиент."""
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import settings
from .heuristics import (
    HeuristicInterpreter as RuleBasedInterpreter,
    build_chat_answer,
)
from .text import clean_list, clean_text, summarize_text


@dataclass
class LLMResult:
    payload: dict[str, Any]
    provider: str
    model: str
    fallback: bool = False
    error: str = ""


@dataclass
class ChatResult:
    answer: str
    provider: str
    model: str
    fallback: bool = False
    error: str = ""

SYSTEM_PROMPT = (
    "Ты — AI-аналитик Альфа-Банка для руководителей крупного бизнеса. "
    "По документу и профилю клиента определи риск, возможность или нейтральное событие, "
    "объясни влияние именно на этого клиента и предложи конкретные действия. "
    "Пиши короткими законченными предложениями, без OCR-артефактов, лишних точек с запятой "
    "и случайного регистра. Не выдумывай цифры, которых нет в документе. "
    "Отвечай строго валидным JSON без markdown-обёрток."
)

USER_TEMPLATE = """Профиль клиента:
{profile}

Документ ({source_type}):
title: {title}
body: {body}
entities: {entities}
industries: {industries}
regions: {regions}

Контекст из аналитических PDF-отчетов Альфа-Банка (RAG):
{rag}

Определи влияние документа на клиента.

Правила:
- kind=risk, если событие может ухудшить выручку, маржу, ликвидность или условия финансирования.
- kind=opportunity, если событие может улучшить выручку, маржу, условия закупок или финансирования.
- kind=neutral только если прямого влияния действительно нет.
- Не называй риск возможностью и наоборот.
- recommended_actions — конкретные выполнимые действия (2-4), без общих фраз.
- cta — короткая кнопка на 2-4 слова.
- Текст должен быть чистым и связным: без OCR-мусора, обрывов и лишних точек с запятой.

Верни JSON:
{{
  "kind": "risk" | "opportunity" | "neutral",
  "confidence": 0.0-1.0,
  "headline": "краткий заголовок до 90 символов",
  "summary": "1-2 предложения: что произошло",
  "details": "3-5 предложений: что произошло подробнее",
  "mechanism": "2-3 предложения: почему это важно именно для этого клиента",
  "affected_business_lines": ["..."],
  "recommended_actions": ["..."],
  "cta": "короткая кнопка",
  "caveats": ["..."]
}}
"""

class LLMClient:
    def __init__(self):
        self.provider = settings.llm_provider
        self.model_name = settings.llm_model
        self._heuristic = RuleBasedInterpreter()

    def interpret_event(
        self, client_ctx: dict, profile: dict, event: dict,
        source_type: str, rag_snippets: list[str],
    ) -> LLMResult:
        # Fallback считаем заранее: он же заполнит поля, которые LLM пропустит.
        fallback = self._heuristic.interpret(
            client_ctx, profile, event, source_type, rag_snippets
        )

        if self.provider == "deepseek" and settings.deepseek_api_key:
            try:
                payload = self._call_deepseek(
                    client_ctx, profile, event, source_type, rag_snippets
                )
                return LLMResult(
                    payload=_normalize_payload(payload, fallback),
                    provider="deepseek",
                    model=self.model_name,
                    fallback=False,
                )
            except Exception as error:
                return LLMResult(
                    payload=fallback,
                    provider="heuristic",
                    model="heuristic-v1",
                    fallback=True,
                    error=str(error),
                )

        return LLMResult(
            payload=fallback,
            provider="heuristic",
            model="heuristic-v1",
            fallback=False,
        )

    def answer_question(
        self,
        question: str,
        client_ctx: dict,
        insight: dict,
        siblings: list[dict],
        rag_snippets: list[str] | None = None,
    ) -> ChatResult:
        fallback = build_chat_answer(question, client_ctx, insight, siblings)

        if self.provider == "deepseek" and settings.deepseek_api_key:
            try:
                answer = self._call_deepseek_chat(
                    question, client_ctx, insight, siblings, rag_snippets or []
                )
                return ChatResult(
                    answer=answer.strip(),
                    provider="deepseek",
                    model=self.model_name,
                    fallback=False,
                )
            except Exception as error:
                return ChatResult(
                    answer=fallback,
                    provider="heuristic",
                    model="heuristic-v1",
                    fallback=True,
                    error=str(error),
                )

        return ChatResult(
            answer=fallback,
            provider="heuristic",
            model="heuristic-v1",
            fallback=False,
        )

    def _post(self, messages: list[dict], temperature: float = 0.2, json_mode: bool = True) -> str:
        url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        with httpx.Client(timeout=settings.tool_timeout_seconds * 3) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise ValueError("DeepSeek вернул пустой ответ")
        return content

    def _call_deepseek(self, client_ctx, profile, event, source_type, rag_snippets) -> dict:
        profile_payload = {
            "industry": client_ctx.get("industry"),
            "scale_revenue_rub": client_ctx.get("scale_revenue_rub"),
            "products": client_ctx.get("products"),
            "regions": client_ctx.get("regions"),
            "counterparties": client_ctx.get("counterparties"),
            "risk_notes": client_ctx.get("risk_notes"),
        }
        user = USER_TEMPLATE.format(
            profile=json.dumps(profile_payload, ensure_ascii=False),
            source_type=source_type,
            title=event.get("title", ""),
            body=event.get("body", ""),
            entities=json.dumps(event.get("entities", []), ensure_ascii=False),
            industries=json.dumps(event.get("industries", []), ensure_ascii=False),
            regions=json.dumps(event.get("regions", []), ensure_ascii=False),
            rag="\n".join(f"- {snippet}" for snippet in rag_snippets[:3]) or "нет",
        )
        content = self._post(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            json_mode=True,
        )
        return _parse_json(content)

    def _call_deepseek_chat(
        self,
        question: str,
        client_ctx: dict,
        insight: dict,
        siblings: list[dict],
        rag_snippets: list[str],
    ) -> str:
        system = (
            "Ты — AI-ассистент Альфа-Бизнеса. Отвечай руководителю крупного бизнеса по-русски. "
            "Используй только предоставленный контекст: профиль клиента, выбранный документ, "
            "сводку по остальным событиям и базу знаний банка. Не выдумывай цифры. "
            "Формат ответа — короткая сводка: вывод, что произошло, почему это важно для клиента, "
            "что можно сделать и ограничения. Пиши короткими предложениями, без markdown."
        )
        context = {
            "client": {
                "name": client_ctx.get("name"),
                "industry": client_ctx.get("industry"),
                "revenue_rub": client_ctx.get("revenueRub"),
                "products": client_ctx.get("products"),
                "regions": client_ctx.get("regions"),
                "payments": client_ctx.get("payments"),
            },
            "selected_document": {
                "title": insight.get("title"),
                "summary": insight.get("summary"),
                "details": insight.get("details"),
                "kind": insight.get("type"),
                "confidence": insight.get("confidence"),
                "mechanism": insight.get("impact"),
                "actions": insight.get("actions"),
                "caveats": insight.get("caveats"),
                "source": insight.get("source"),
            },
            "other_events": [
                {
                    "title": item.get("title"),
                    "kind": item.get("type"),
                    "summary": item.get("summary"),
                }
                for item in siblings[:6]
            ],
        }
        user = (
            "Контекст:\n"
            + json.dumps(context, ensure_ascii=False, indent=2)
            + "\n\nБаза знаний банка:\n"
            + ("\n".join(f"- {snippet}" for snippet in rag_snippets[:4]) or "нет")
            + f"\n\nВопрос клиента: {question}\n\n"
            + "Ответь структурированной сводкой. Если данных не хватает, честно скажи об этом."
        )
        return self._post(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            json_mode=False,
        )

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _normalize_payload(payload: dict, fallback: dict) -> dict:
    """Приводит ответ LLM к единому виду и чистит текст."""
    merged = dict(fallback)
    for key, value in (payload or {}).items():
        if value not in (None, "", [], {}):
            merged[key] = value

    kind = str(merged.get("kind") or "neutral").lower()
    if kind not in {"risk", "opportunity", "neutral"}:
        kind = fallback.get("kind", "neutral")
    merged["kind"] = kind

    try:
        confidence = float(merged.get("confidence"))
    except (TypeError, ValueError):
        confidence = float(fallback.get("confidence", 0.5))
    merged["confidence"] = round(max(0.0, min(1.0, confidence)), 2)

    merged["headline"] = clean_text(
        str(merged.get("headline") or fallback.get("headline") or "")
    )[:140]
    merged["summary"] = (
        summarize_text(str(merged.get("summary") or ""), max_sentences=2, max_chars=280)
        or fallback.get("summary", "")
    )
    merged["details"] = (
        summarize_text(str(merged.get("details") or ""), max_sentences=5, max_chars=700)
        or fallback.get("details", "")
        or merged["summary"]
    )
    merged["mechanism"] = (
        summarize_text(str(merged.get("mechanism") or ""), max_sentences=3, max_chars=420)
        or fallback.get("mechanism", "")
    )
    merged["affected_business_lines"] = clean_list(
        merged.get("affected_business_lines") or fallback.get("affected_business_lines"),
        limit=4,
    )
    merged["recommended_actions"] = clean_list(
        merged.get("recommended_actions") or fallback.get("recommended_actions"),
        limit=5,
    )
    merged["caveats"] = clean_list(
        merged.get("caveats") or fallback.get("caveats"),
        limit=2,
    )
    merged["cta"] = (
        clean_text(str(merged.get("cta") or fallback.get("cta") or ""))[:40]
        or "Мониторинг"
    )
    return merged