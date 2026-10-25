"""ETL-скрипт для загрузки реальных (обезличенных) данных заказчика.
Запуск: python -m app.ingest_csv
"""
import os
import pandas as pd
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .metrics import build_payment_stats, save_payment_stats
from .models import (
    Client, ClientProfile, EventInsight, RunStep, 
    ToolLog, AnalysisRun
)

FILE_PROFILE = "data/raw/df_Uid_data_hack.csv"
FILE_PAYMENTS = "data/raw/df_Uid_payment_hack.csv"

# Флаги продуктов называются *_MARK — именно они есть в выгрузке заказчика.
PRODUCT_FLAGS = [
    ("CL_PRODUCT_RKO_MARK", "РКО"),
    ("CL_PRODUCT_GAR_MARK", "Гарантии"),
    ("CL_PRODUCT_LOA_MARK", "Кредиты"),
    ("CL_PRODUCT_LEA_MARK", "Лизинг"),
    ("CL_PRODUCT_DEP_MARK", "Депозиты"),
    ("CL_PRODUCT_ZPP_MARK", "Зарплатный проект"),
]


def _flag(value) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return pd.notna(number) and number != 0.0


def _parse_products(row):
    return [name for column, name in PRODUCT_FLAGS if _flag(row.get(column))]


def run_ingestion():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    print("Очищаем старую базу данных...")
    db.query(EventInsight).delete()
    db.query(RunStep).delete()
    db.query(ToolLog).delete()
    db.query(AnalysisRun).delete()
    db.query(ClientProfile).delete()
    db.query(Client).delete()
    db.commit()

    print("Читаем CSV файлы...")
    try:
        df_profile = pd.read_csv(FILE_PROFILE, sep=';', encoding='utf-8', on_bad_lines='skip')
        df_payments = pd.read_csv(FILE_PAYMENTS, sep=';', encoding='utf-8', on_bad_lines='skip')
    except UnicodeDecodeError:
        print("Переключение кодировки на cp1251...")
        df_profile = pd.read_csv(FILE_PROFILE, sep=';', encoding='cp1251', on_bad_lines='skip')
        df_payments = pd.read_csv(FILE_PAYMENTS, sep=';', encoding='cp1251', on_bad_lines='skip')

    df_profile.columns = [str(c).strip() for c in df_profile.columns]
    df_payments.columns = [str(c).strip() for c in df_payments.columns]

    if "SYNTHETIC_U" in df_profile.columns:
        df_profile = df_profile.drop_duplicates(subset=["SYNTHETIC_U"])

    print("Формируем клиентов...")
    for _, row in df_profile.iterrows():
        uid_val = row.get("SYNTHETIC_U")
        if pd.isna(uid_val):
            continue
        uid = str(uid_val).strip()
        
        client_name = f'ООО "Клиент {uid}"'
        
        # Численность в выгрузке задана диапазоном, а не точным числом.
        workers_raw = row.get("AMOUNT_WORKERS_FNS_GRADATION") or ""
        workers_range = str(workers_raw).strip() if pd.notna(workers_raw) else ""

        revenue_raw = row.get("REVENUE_COMPANY") or 0.0
        revenue = float(revenue_raw) if pd.notna(revenue_raw) else 0.0

        industry_raw = row.get("MAINOKVED_NAME") or "Не указана"
        industry = str(industry_raw).strip() if pd.notna(industry_raw) else "Не указана"

        region_raw = row.get("REGION") or "Не указан"
        region = str(region_raw).strip() if pd.notna(region_raw) else "Не указан"
        city_raw = row.get("CITY") or ""
        city = str(city_raw).strip() if pd.notna(city_raw) else ""

        negative = _flag(row.get("NEGATIVEMARK"))
        eco_mark = str(row.get("ECO_MARK_LABEL") or "—").strip()
        client_type = str(row.get("CL_TYPE") or "—").strip()
        age = str(row.get("COMPANY_AGE_YEARS_GRADATION") or "—").strip()

        risk_notes = (
            f"Негативные маркеры: {'есть' if negative else 'нет'}. "
            f"Эко-маркер: {eco_mark}."
        )

        client = Client(
            name=client_name,
            industry=industry,
            scale_employees=0,
            scale_revenue_rub=revenue,
            description=(
                f"Тип клиента: {client_type}. Возраст: {age} лет. "
                f"Регион: {region}. Численность: {workers_range or '—'}."
            ),
        )
        db.add(client)
        db.flush()

        profile = ClientProfile(
            client_id=client.id,
            products=_parse_products(row),
            regions=[r for r in [region, city] if r],
            keywords=[industry] if industry != "Не указана" else [],
            risk_notes=risk_notes
        )
        db.add(profile)
    
    db.commit()
    print(f"Успешно загружено {db.query(Client).count()} клиентов.")

    print("Строим граф контрагентов (оптимизированный метод)...")
    
    # Очищаем суммы от NaN и приводим к числу
    df_payments['PAY_AMT'] = pd.to_numeric(df_payments['PAY_AMT'], errors='coerce').fillna(0)
    
    # 1. Оптимизация: Группируем транзакции ЗАРАНЕЕ через Pandas
    # Поставщики (кому платит клиент)
    grouped_suppliers = df_payments.groupby(['PAYER', 'BENEFICIARY'])['PAY_AMT'].sum().reset_index()
    top_suppliers = grouped_suppliers.sort_values(['PAYER', 'PAY_AMT'], ascending=[True, False]).groupby('PAYER').head(5)
    
    # Формируем словарь: { 'U_123': [{'name': 'U_456', 'amount': 1000}, ...] }
    suppliers_dict = {}
    for _, row in top_suppliers.iterrows():
        suppliers_dict.setdefault(row['PAYER'], []).append({
            'name': row['BENEFICIARY'],
            'amount': row['PAY_AMT']
        })

    # Покупатели (кто платит клиенту)
    grouped_customers = df_payments.groupby(['BENEFICIARY', 'PAYER'])['PAY_AMT'].sum().reset_index()
    top_customers = grouped_customers.sort_values(['BENEFICIARY', 'PAY_AMT'], ascending=[True, False]).groupby('BENEFICIARY').head(5)
    
    customers_dict = {}
    for _, row in top_customers.iterrows():
        customers_dict.setdefault(row['BENEFICIARY'], []).append({
            'name': row['PAYER'],
            'amount': row['PAY_AMT']
        })

    # 2. Обновляем профили в БД за один проход
    for client in db.query(Client).all():
        uid = client.name.split()[-1].strip('"')
        
        counterparties = []
        # Достаем заранее подготовленных поставщиков из словаря
        for s in suppliers_dict.get(uid, []):
            counterparties.append({
                "name": f"ООО Поставщик {s['name']}",
                "role": "supplier",
                "share": f"{s['amount'] / 1e6:.1f} млн руб."
            })
        # Достаем заранее подготовленных покупателей из словаря
        for c in customers_dict.get(uid, []):
            counterparties.append({
                "name": f"ООО Покупатель {c['name']}",
                "role": "customer",
                "share": f"{c['amount'] / 1e6:.1f} млн руб."
            })
            
        if client.profile and counterparties:
            client.profile.counterparties = counterparties
            db.add(client.profile)

    db.commit()

    print("Сохраняем агрегаты платежей для дашборда...")
    payment_stats = build_payment_stats(df_payments)
    known_uids = {str(value).strip() for value in df_profile["SYNTHETIC_U"].dropna()}
    save_payment_stats({
        uid: values for uid, values in payment_stats.items() if uid in known_uids
    })
    print(f"Сохранено агрегатов: {len(payment_stats)}")

    db.close()
    print("✅ Импорт завершен! Теперь можно запускать сервер.")


if __name__ == "__main__":
    run_ingestion()