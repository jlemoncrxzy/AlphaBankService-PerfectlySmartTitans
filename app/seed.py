"""Синтетические данные: 3 клиента, 3 пользователя (роли), ~14 новостей,
5 аналитик Альфа-Банка. Включает шум и неполные записи для проверки устойчивости."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import User, Client, ClientProfile, NewsItem, BankAnalytic
from .security import hash_password


def _dt(days_ago: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days_ago)


def seed():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return  # уже засеяно

        # --- Пользователи (тестовые учётки) ---
        db.add_all([
            User(username="admin",   password_hash=hash_password("admin123"),   role="admin"),
            User(username="analyst", password_hash=hash_password("analyst123"), role="analyst"),
            User(username="viewer",  password_hash=hash_password("viewer123"),  role="viewer"),
        ])
        db.flush()

        # --- Клиенты ---
        c1 = Client(
            name='ПАО "МеталлПром"', industry="Металлургия",
            scale_revenue_rub=120_000_000_000, scale_employees=15_000,
            description="Крупный производитель горячекатаного проката и труб. "
                        "Экспорт в СНГ, зависимость от коксующегося угля. "
                        "Ключевые регионы — Свердловская и Челябинская области.",
        )
        c2 = Client(
            name='ООО "АгроХолдинг Кубань"', industry="Агропром",
            scale_revenue_rub=45_000_000_000, scale_employees=8_000,
            description="Производство и экспорт зерна (пшеница, кукуруза, подсолнечник). "
                        "Зависимость от экспортных пошлин и урожайности. "
                        "Регионы — Краснодарский край, Ростовская область.",
        )
        c3 = Client(
            name='ООО "ТехноСофт"', industry="IT",
            scale_revenue_rub=8_000_000_000, scale_employees=2_500,
            description="Разработчик ERP-решений и систем кибербезопасности. "
                        "Программа импортозамещения ПО, зависимость от ЦОД и кадров. "
                        "Регионы — Москва, Санкт-Петербург.",
        )
        db.add_all([c1, c2, c3]); db.flush()

        db.add_all([
            ClientProfile(
                client_id=c1.id,
                products=["горячекатаный прокат", "трубы", "арматура"],
                counterparties=[
                    {"name": "Уголь-Юг",     "role": "supplier",   "share": "40%"},
                    {"name": "АвтоВаз",      "role": "customer",   "share": "25%"},
                    {"name": "Сталь-Инвест", "role": "competitor", "share": ""},
                ],
                regions=["Свердловская область", "Челябинская область", "Кемеровская область"],
                keywords=["экспорт", "коксующийся уголь", "логистика", "ставка"],
                risk_notes="Высокая зависимость от поставщика угля и автопрома.",
            ),
            ClientProfile(
                client_id=c2.id,
                products=["пшеница", "кукуруза", "подсолнечник"],
                counterparties=[
                    {"name": "Семена-Юг",     "role": "supplier",   "share": "30%"},
                    {"name": "ЭкспортЗерно",  "role": "customer",   "share": "50%"},
                    {"name": "Кубань-Агро",   "role": "competitor", "share": ""},
                ],
                regions=["Краснодарский край", "Ростовская область"],
                keywords=["экспорт", "зерно", "урожай", "пошлина", "санкции"],
                risk_notes="Экспортная пошлина и логистика — ключевые риски.",
            ),
            ClientProfile(
                client_id=c3.id,
                products=["ERP-решения", "кибербезопасность"],
                counterparties=[
                    {"name": "Клауд-Сервис",  "role": "supplier",   "share": "30%"},
                    {"name": "Ритейл-Сеть Х", "role": "customer",   "share": "20%"},
                    {"name": "Цифра-Плюс",    "role": "competitor", "share": ""},
                ],
                regions=["Москва", "Санкт-Петербург"],
                keywords=["импортозамещение", "ЦОД", "кадры", "кибератака"],
                risk_notes="Зависимость от облачного провайдера и дефицит кадров.",
            ),
        ])

        # --- Новости (включая шум: пустые entities, неоднозначные) ---
        news = [
            NewsItem(title="Рост цен на коксующийся уголь в Кузбассе на 18%",
                     body="По итогам квартала цены на коксующийся уголь выросли на 18% из-за логистических ограничений. "
                          "Основные потребители — металлургические комбинаты Урала.",
                     source="Ведомости", published_at=_dt(2),
                     entities=["Уголь-Юг", "Кузбасс"], industries=["Металлургия"],
                     regions=["Кемеровская область", "Свердловская область"], magnitude=0.9),
            NewsItem(title="АвтоВаз снижает производство на 15% во II квартале",
                     body="АвтоВаз объявил о сокращении выпуска на 15% из-за падения спроса. "
                          "Поставщики металлопроката ощутят снижение заказов.",
                     source="Коммерсантъ", published_at=_dt(1),
                     entities=["АвтоВаз"], industries=["Автопром", "Металлургия"],
                     regions=["Самарская область"], magnitude=0.85),
            NewsItem(title="Новая экспортная пошлина на пшеницу с 1 июля",
                     body="Правительство вводит плавающую экспортную пошлину на пшеницу. "
                          "Ожидается давление на маржу экспортёров зерна.",
                     source="РБК", published_at=_dt(3),
                     entities=["ЭкспортЗерно"], industries=["Агропром"],
                     regions=["Краснодарский край", "Ростовская область"], magnitude=0.9),
            NewsItem(title="Засуха в Краснодарском крае: прогноз урожая снижен на 12%",
                     body="Из-за аномальной жары аналитики снизили прогноз урожая пшеницы. "
                          "Под угрозой — экспортные контракты.",
                     source="Интерфакс", published_at=_dt(4),
                     entities=[], industries=["Агропром"],
                     regions=["Краснодарский край"], magnitude=0.8),
            NewsItem(title="Крупная кибератака на логистического оператора",
                     body="Хакеры атаковали ИТ-инфраструктуру логистической компании. "
                          "Пострадали клиенты из ритейла и промышленности.",
                     source="SecurityLab", published_at=_dt(1),
                     entities=["Клауд-Сервис"], industries=["Логистика", "IT", "Ритейл"],
                     regions=["Москва"], magnitude=0.7),
            NewsItem(title="ЦБ повысил ключевую ставку на 100 б.п.",
                     body="Банк России повысил ставку. Удорожание кредитов затронет капиталоёмкие отрасли.",
                     source="ЦБ РФ", published_at=_dt(5),
                     entities=[], industries=["Металлургия", "Агропром", "IT", "Строительство"],
                     regions=["Россия"], magnitude=0.8),
            NewsItem(title="Сталь-Инвест останавливает доменную печь на ремонт",
                     body="Конкурент МеталлПрома остановил производство на 2 месяца. "
                          "Возможен переток заказов.",
                     source="Металл-Инфо", published_at=_dt(2),
                     entities=["Сталь-Инвест"], industries=["Металлургия"],
                     regions=["Челябинская область"], magnitude=0.6),
            NewsItem(title="Господдержка импортозамещения ПО расширена",
                     body="Правительство увеличило субсидии на импортозамещение ERP и систем безопасности.",
                     source="CNews", published_at=_dt(6),
                     entities=[], industries=["IT"],
                     regions=["Москва"], magnitude=0.7),
            NewsItem(title="Дефицит IT-кадров усиливается: зарплаты выросли на 22%",
                     body="Рынок IT-специалистов остаётся перегретым. Компании повышают ФОТ.",
                     source="Habr", published_at=_dt(3),
                     entities=[], industries=["IT"],
                     regions=["Москва", "Санкт-Петербург"], magnitude=0.6),
            NewsItem(title="Открыт новый логистический коридор Север-Юг",
                     body="Запущен коридор для экспорта металлов и зерна через Каспий.",
                     source="Логистика сегодня", published_at=_dt(7),
                     entities=[], industries=["Металлургия", "Агропром", "Логистика"],
                     regions=["Россия"], magnitude=0.6),
            # шум / неполные данные
            NewsItem(title="Небольшой пожар на складе в Подмосковье",
                     body="", source="МЧС", published_at=_dt(8),
                     entities=[], industries=[], regions=["Московская область"], magnitude=0.2),
            NewsItem(title="Аномальная жара в Европе",
                     body="Температурные рекорды в Испании и Италии.",
                     source="Euronews", published_at=_dt(2),
                     entities=[], industries=[], regions=["Европа"], magnitude=0.3),
            NewsItem(title="Ритейл-Сеть Х открывает 20 новых магазинов",
                     body="Расширение сети в регионах присутствия. Возможен рост ИТ-закупок.",
                     source="Retail.ru", published_at=_dt(1),
                     entities=["Ритейл-Сеть Х"], industries=["Ритейл", "IT"],
                     regions=["Москва", "Санкт-Петербург"], magnitude=0.55),
            NewsItem(title="Кубань-Агро покупает новый элеватор",
                     body="Конкурент АгроХолдинга расширяет мощности хранения.",
                     source="Агро-Инвест", published_at=_dt(3),
                     entities=["Кубань-Агро"], industries=["Агропром"],
                     regions=["Краснодарский край"], magnitude=0.5),
        ]
        db.add_all(news)

        analytics = [
            BankAnalytic(title="Ставка ЦБ и капиталоёмкие отрасли: взгляд Альфа-Банка",
                         body="Повышение ставки на 100 б.п. увеличит стоимость заёмного финансирования. "
                              "Для металлургии и агросектора рекомендуем пересмотреть инвестиционные программы.",
                         category="Макро", published_at=_dt(4),
                         entities=[], industries=["Металлургия", "Агропром", "IT"],
                         regions=["Россия"], magnitude=0.85),
            BankAnalytic(title="Импортозамещение ПО: окно возможностей для российских вендоров",
                         body="Субсидии и уход западных вендоров создают окно для ERP-решений. "
                              "Риск — дефицит кадров и нагрузка на ЦОД.",
                         category="Отрасль", published_at=_dt(5),
                         entities=[], industries=["IT"],
                         regions=["Москва", "Санкт-Петербург"], magnitude=0.75),
            BankAnalytic(title="Зерновой экспорт: пошлины и логистика",
                         body="Плавающая пошлина и ограничения логистики давят на маржу экспортёров. "
                              "Коридор Север-Юг может частично компенсировать.",
                         category="Отрасль", published_at=_dt(3),
                         entities=["ЭкспортЗерно"], industries=["Агропром"],
                         regions=["Краснодарский край", "Ростовская область"], magnitude=0.8),
            BankAnalytic(title="Логистические коридоры и металлургия",
                         body="Север-Юг открывает альтернативные маршруты для проката. "
                              "Требует перестройки цепочек поставок.",
                         category="Логистика", published_at=_dt(6),
                         entities=[], industries=["Металлургия", "Логистика"],
                         regions=["Россия"], magnitude=0.65),
            BankAnalytic(title="Киберриски в цепочках поставок",
                         body="Атаки на логистику и облачных провайдеров создают операционные риски. "
                              "Рекомендуется аудит контрагентов-провайдеров ИТ-услуг.",
                         category="Риски", published_at=_dt(2),
                         entities=["Клауд-Сервис"], industries=["IT", "Логистика", "Ритейл"],
                         regions=["Москва"], magnitude=0.7),
        ]
        db.add_all(analytics)
        db.commit()
    finally:
        db.close()