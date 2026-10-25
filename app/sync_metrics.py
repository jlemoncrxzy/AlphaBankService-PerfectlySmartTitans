"""Синхронизация профилей клиентов с исходными выгрузками.

Скрипт обновляет только справочные метрики (выручка, продукты, регионы,
описание) и пересобирает кэш платёжных агрегатов. Аналитика
(analysis_runs / event_insights) не затрагивается.

Запуск: python -m app.sync_metrics
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd

from .config import settings
from .metrics import build_payment_stats, save_payment_stats

PROFILE_CSV = Path("data/raw/df_Uid_data_hack.csv")
PAYMENTS_CSV = Path("data/raw/df_Uid_payment_hack.csv")

PRODUCT_FLAGS = [
    ("CL_PRODUCT_RKO_MARK", "РКО"),
    ("CL_PRODUCT_GAR_MARK", "Гарантии"),
    ("CL_PRODUCT_LOA_MARK", "Кредиты"),
    ("CL_PRODUCT_LEA_MARK", "Лизинг"),
    ("CL_PRODUCT_DEP_MARK", "Депозиты"),
    ("CL_PRODUCT_ZPP_MARK", "Зарплатный проект"),
]


def _read_csv(path: Path) -> pd.DataFrame:
    last_error = None
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            frame = pd.read_csv(path, sep=";", encoding=encoding, on_bad_lines="skip")
            frame.columns = [str(column).strip() for column in frame.columns]
            return frame
        except UnicodeDecodeError as error:  # пробуем следующую кодировку
            last_error = error
    raise RuntimeError(f"Не удалось прочитать {path}: {last_error}")


def _number(value, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _flag(value) -> bool:
    return _number(value) != 0.0


def _products(row) -> list[str]:
    return [name for column, name in PRODUCT_FLAGS if _flag(row.get(column))]


def _sqlite_path() -> str:
    return settings.database_url.removeprefix("sqlite:///")


def sync_clients(profile: pd.DataFrame, connection: sqlite3.Connection) -> int:
    ids_by_name = {
        name: client_id
        for client_id, name in connection.execute("SELECT id, name FROM clients")
    }

    client_updates = []
    profile_updates = []
    for _, row in profile.iterrows():
        uid_value = row.get("SYNTHETIC_U")
        if pd.isna(uid_value):
            continue
        uid = str(uid_value).strip()
        client_id = ids_by_name.get(f'ООО "Клиент {uid}"')
        if client_id is None:
            continue

        industry = _text(row.get("MAINOKVED_NAME"))
        region = _text(row.get("REGION"))
        city = _text(row.get("CITY"))
        age = _text(row.get("COMPANY_AGE_YEARS_GRADATION"))
        workers = _text(row.get("AMOUNT_WORKERS_FNS_GRADATION"))
        client_type = _text(row.get("CL_TYPE"))
        negative = _flag(row.get("NEGATIVEMARK"))
        eco = _text(row.get("ECO_MARK_LABEL"))

        revenue = _number(row.get("REVENUE_COMPANY"))
        description = (
            f"Тип клиента: {client_type or '—'}. Возраст: {age or '—'} лет. "
            f"Регион: {region or '—'}. Численность: {workers or '—'}."
        )
        risk_notes = (
            f"Негативные маркеры: {'есть' if negative else 'нет'}. "
            f"Эко-маркер: {eco or '—'}."
        )
        regions = [value for value in dict.fromkeys([region, city]) if value]
        keywords = [industry] if industry else []

        client_updates.append((revenue, description, client_id))
        profile_updates.append((
            json.dumps(_products(row), ensure_ascii=False),
            json.dumps(regions, ensure_ascii=False),
            json.dumps(keywords, ensure_ascii=False),
            risk_notes,
            client_id,
        ))

    with connection:
        connection.executemany(
            "UPDATE clients SET scale_revenue_rub = ?, description = ? WHERE id = ?",
            client_updates,
        )
        connection.executemany(
            "UPDATE client_profiles SET products = ?, regions = ?, keywords = ?, risk_notes = ? "
            "WHERE client_id = ?",
            profile_updates,
        )
    return len(client_updates)


def sync_payments(payments: pd.DataFrame, known_uids: set[str]) -> int:
    stats = build_payment_stats(payments)
    filtered = {uid: values for uid, values in stats.items() if uid in known_uids}
    save_payment_stats(filtered)
    return len(filtered)


def run() -> None:
    print("Читаем выгрузки…")
    profile = _read_csv(PROFILE_CSV)
    payments = _read_csv(PAYMENTS_CSV)

    known_uids = {
        str(value).strip()
        for value in profile["SYNTHETIC_U"].dropna()
    }

    connection = sqlite3.connect(_sqlite_path())
    try:
        updated = sync_clients(profile, connection)
        print(f"Обновлено клиентов: {updated}")
    finally:
        connection.close()

    written = sync_payments(payments, known_uids)
    print(f"Платёжных агрегатов сохранено: {written}")


if __name__ == "__main__":
    run()
