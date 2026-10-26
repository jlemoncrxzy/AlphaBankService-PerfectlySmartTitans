"""API раздела «Контрагенты».

Отдаёт граф контрагентов клиента из платёжной выгрузки: топ-поставщики и
топ-покупатели по сумме операций, доли в обороте и оценку концентрации.
Все цифры считаются из реальных данных профиля, без демо-заглушек.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import AnalysisRun, Client
from .dashboard import _number, _payment_stats, _uid, format_client

router = APIRouter(prefix="/api", tags=["counterparties"])

ROLE_LABELS = {"supplier": "Поставщик", "customer": "Покупатель"}
ROLE_DIRECTIONS = {
    "supplier": "Исходящие платежи",
    "customer": "Входящие платежи",
}

# В выгрузке контрагенты обезличены: «ООО Поставщик U_107639».
NAME_PREFIX = re.compile(
    r"^(?:ООО|АО|ОАО|ЗАО|ПАО|ИП)\s+(?:Поставщик|Покупатель)\s+",
    re.IGNORECASE,
)
MONEY = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*(млрд|млн|тыс)?", re.IGNORECASE)
MULTIPLIERS = {"млрд": 1e9, "млн": 1e6, "тыс": 1e3}

# Порог, с которого зависимость от одного контрагента считаем опасной.
CONCENTRATION_HIGH = 50.0
CONCENTRATION_MEDIUM = 30.0


def _parse_money(value: str) -> float | None:
    """«22.3 млн руб.» → 22_300_000. Нужно для старых профилей, где сумма — строка."""
    match = MONEY.search(value.replace("\u00a0", " "))
    if not match:
        return None
    try:
        number = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    return number * MULTIPLIERS.get((match.group(2) or "").lower(), 1.0)


def _amount_rub(item: dict) -> float:
    for key in ("amountRub", "amount"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            parsed = _parse_money(value)
            if parsed:
                return parsed
    return _parse_money(str(item.get("share") or "")) or 0.0


def _clean_name(raw: str) -> str:
    cleaned = NAME_PREFIX.sub("", raw).strip()
    return cleaned or raw


def _concentration_level(top_share: float) -> tuple[str, str]:
    if top_share >= CONCENTRATION_HIGH:
        return "high", "Высокая"
    if top_share >= CONCENTRATION_MEDIUM:
        return "medium", "Умеренная"
    return "low", "Низкая"


def _resolve_client(db: Session, company_id: str | None) -> Client:
    """Компания из запроса или та же, что показывает дашборд по умолчанию."""
    if company_id:
        try:
            client = (
                db.query(Client)
                .options(joinedload(Client.profile))
                .filter(Client.id == int(company_id))
                .first()
            )
        except ValueError:
            client = None
        if client is None:
            raise HTTPException(404, "Клиент не найден")
        return client

    latest_run = (
        db.query(AnalysisRun)
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
        .first()
    )
    query = db.query(Client).options(joinedload(Client.profile))
    if latest_run:
        client = query.filter(Client.id == latest_run.client_id).first()
        if client is not None:
            return client

    client = query.order_by(Client.id).first()
    if client is None:
        raise HTTPException(404, "В базе нет клиентов")
    return client


def _counterparty_items(client: Client) -> tuple[list[dict], int]:
    profile = client.profile
    raw_items = list(profile.counterparties or []) if profile else []

    parsed: list[dict] = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            continue
        raw_name = str(raw.get("name") or "").strip()
        if not raw_name:
            continue
        role = str(raw.get("role") or "").lower()
        amount = _amount_rub(raw)
        parsed.append({
            "id": f"{client.id}-{index}",
            "name": _clean_name(raw_name),
            "rawName": raw_name,
            "role": role if role in ROLE_LABELS else "other",
            "roleLabel": ROLE_LABELS.get(role, "Контрагент"),
            "direction": ROLE_DIRECTIONS.get(role, "Операции с контрагентом"),
            "amountRub": round(amount, 2),
        })

    # В выгрузке суммы округлены до 0,1 млн ₽: контрагенты с нулевым оборотом
    # в таблицу не попадают, но их количество показываем отдельно.
    items = [item for item in parsed if item["amountRub"] > 0]
    low_value = len(parsed) - len(items)

    total = sum(item["amountRub"] for item in items)
    for item in items:
        item["share"] = round(item["amountRub"] / total * 100, 1) if total else 0.0

    items.sort(key=lambda item: item["amountRub"], reverse=True)
    return items, low_value


@router.get("/counterparties")
def get_counterparties(
    companyId: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    client = _resolve_client(db, companyId)
    payment_stats = _payment_stats()
    items, low_value_count = _counterparty_items(client)

    suppliers = [item for item in items if item["role"] == "supplier"]
    customers = [item for item in items if item["role"] == "customer"]
    top = items[0] if items else None
    total = sum(item["amountRub"] for item in items)
    top3_share = round(sum(item["share"] for item in items[:3]), 1)
    level, level_label = _concentration_level(top["share"] if top else 0.0)
    stats = payment_stats.get(_uid(client.name) or "", {}) or {}

    return {
        "company": format_client(client, 0, payment_stats),
        "summary": {
            "count": len(items),
            "suppliers": len(suppliers),
            "customers": len(customers),
            "totalAmountRub": round(total, 2),
            "supplierAmountRub": round(sum(item["amountRub"] for item in suppliers), 2),
            "customerAmountRub": round(sum(item["amountRub"] for item in customers), 2),
            "topShare": top["share"] if top else 0.0,
            "top3Share": top3_share,
            "lowValueCount": low_value_count,
            "concentration": {"level": level, "label": level_label},
            "top": (
                {
                    "name": top["name"],
                    "role": top["role"],
                    "roleLabel": top["roleLabel"],
                    "amountRub": top["amountRub"],
                    "share": top["share"],
                }
                if top
                else None
            ),
        },
        "payments": {
            "hasData": bool(stats),
            "incomingRub": _number(stats.get("in")),
            "outgoingRub": _number(stats.get("out")),
            "incomingCounterparties": int(stats.get("inCp") or 0),
            "outgoingCounterparties": int(stats.get("outCp") or 0),
        },
        "items": items,
        "meta": {
            "source": "Платёжная выгрузка банка",
            "anonymous": True,
            "note": "Топ-5 поставщиков и топ-5 покупателей по сумме операций.",
        },
    }
