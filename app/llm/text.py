"""Локальная очистка и форматирование текста.

DeepSeek может быть недоступен (нет ключа, сеть, лимиты), поэтому базовое
«причёсывание» должно работать детерминированно: убираем OCR-артефакты,
разбиваем текст на предложения и собираем короткие сводки.
"""
import re

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Частые OCR-артефакты в PDF-выгрузках Альфа-Банка.
UPPER_WORD_FIXES = {
    "ЧТО": "что",
    "ПО": "по",
    "НА": "на",
    "ДЛЯ": "для",
    "КАК": "как",
    "ПРИ": "при",
    "ИЛИ": "или",
    "ЭТО": "это",
    "ТАК": "так",
    "УЖЕ": "уже",
    "ЕЩЕ": "ещё",
}

BOILERPLATE_PATTERNS = [
    re.compile(
        r"^[AА]\s+Центр макроэкономического анализа\b.*?\b\d{4}\s*(?:года|г\.|г|r:|:)?\s*",
        re.IGNORECASE,
    ),
    re.compile(r"^[AА]\s+Аналитический центр\s+", re.IGNORECASE),
    re.compile(r"^[AА]\s+Альфа-?Банк\s+", re.IGNORECASE),
    re.compile(r"^[AА]\s+(?=[А-ЯЁA-Z])"),
]


def _capitalize_sentences(text: str) -> str:
    def upper(match: re.Match) -> str:
        return match.group(1) + match.group(2).upper()

    return re.sub(r"(^|[.!?]\s+)([а-яё])", upper, text)


def clean_text(value: str | None) -> str:
    """Приводит текст к аккуратному виду, не меняя его смысл."""
    text = (value or "").replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    for pattern in BOILERPLATE_PATTERNS:
        text = pattern.sub("", text).strip()

    for source, target in UPPER_WORD_FIXES.items():
        text = re.sub(rf"\b{source}\b", target, text)

    # Латинские «A» и «c» — частые OCR-артефакты русских PDF.
    text = re.sub(r"\s+A\s+", " ", text)
    text = re.sub(r"\bc\b", "с", text)

    # В PDF-выгрузках точка с запятой часто заменяет границу предложения.
    text = text.replace(";", ". ")
    text = re.sub(r"\s*:\s*(?!\d)", ": ", text)
    text = re.sub(r"\s*,\s*(?!\d)", ", ", text)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\.\s*(?=[А-ЯЁA-Z])", ". ", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _capitalize_sentences(text)
    return text.strip()


def split_sentences(value: str | None) -> list[str]:
    cleaned = clean_text(value)
    if not cleaned:
        return []
    return [part.strip() for part in SENTENCE_SPLIT.split(cleaned) if part.strip()]


def summarize_text(value: str | None, max_sentences: int = 2, max_chars: int = 260) -> str:
    """Короткая сводка по первым предложениям документа."""
    sentences = split_sentences(value)
    if not sentences:
        return ""

    selected: list[str] = []
    length = 0
    for sentence in sentences[:max_sentences]:
        remaining = max_chars - length
        if remaining <= 0:
            break
        if len(sentence) <= remaining:
            selected.append(sentence)
            length += len(sentence) + 1
            continue
        if not selected:
            truncated = sentence[:remaining].rsplit(" ", 1)[0].rstrip(".,;:")
            selected.append(truncated + "…")
        break

    summary = " ".join(selected).strip()
    if summary and not summary.endswith((".", "!", "?", "…")):
        summary += "."
    return summary


def headline_from_text(value: str | None, fallback: str = "") -> str:
    """Человекочитаемый заголовок из первых предложений документа."""
    sentences = split_sentences(value)
    if not sentences:
        return clean_text(fallback)

    first = sentences[0].rstrip(".")
    second = sentences[1].rstrip(".") if len(sentences) > 1 else ""

    if second and len(first) <= 34:
        second = second[:1].lower() + second[1:]
        headline = f"{first}: {second}"
    else:
        headline = first

    headline = headline.strip(" .")
    if len(headline) > 92:
        headline = headline[:92].rsplit(" ", 1)[0].rstrip(".,;:") + "…"
    return headline or clean_text(fallback)


def clean_list(values, limit: int = 4) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = clean_text(str(value)).rstrip(".")
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def is_filename(title: str | None) -> bool:
    text = (title or "").strip().lower()
    return text.endswith(".pdf") or ("_" in text and any(ch.isascii() and ch.isalpha() for ch in text))
