"""Агрегаты по платёжной выгрузке.

Модуль не зависит от FastAPI и ORM: считает реальные суммы входящих
и исходящих платежей по каждому клиенту и сохраняет их в JSON-кэш.
Дашборд читает кэш, а не 38-мегабайтный CSV на каждый запрос.
"""
import json
from pathlib import Path

import pandas as pd

PAYMENT_STATS_PATH = Path("data/payment_stats.json")


def build_payment_stats(df: pd.DataFrame) -> dict:
    """Считает обороты и число контрагентов по каждому SYNTHETIC_U."""
    data = df.copy()
    data["PAY_AMT"] = pd.to_numeric(data["PAY_AMT"], errors="coerce").fillna(0.0)
    data["PAY_CNT"] = pd.to_numeric(data["PAY_CNT"], errors="coerce").fillna(0)

    outgoing = data.groupby("PAYER", sort=False).agg(
        out=("PAY_AMT", "sum"),
        outTx=("PAY_CNT", "sum"),
        outCp=("BENEFICIARY", "nunique"),
    )
    incoming = data.groupby("BENEFICIARY", sort=False).agg(
        inn=("PAY_AMT", "sum"),
        inTx=("PAY_CNT", "sum"),
        inCp=("PAYER", "nunique"),
    )
    merged = outgoing.join(incoming, how="outer").fillna(0)

    stats: dict[str, dict] = {}
    for uid, row in merged.iterrows():
        stats[str(uid)] = {
            "in": round(float(row["inn"]), 2),
            "out": round(float(row["out"]), 2),
            "inTx": int(row["inTx"]),
            "outTx": int(row["outTx"]),
            "inCp": int(row["inCp"]),
            "outCp": int(row["outCp"]),
        }
    return stats


def save_payment_stats(stats: dict, path: Path = PAYMENT_STATS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(stats, file, ensure_ascii=False)


def load_payment_stats(path: Path = PAYMENT_STATS_PATH) -> dict:
    """Читает кэш агрегатов. Пустой словарь, если кэша ещё нет."""
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
