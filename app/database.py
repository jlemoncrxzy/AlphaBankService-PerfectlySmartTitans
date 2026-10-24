"""SQLAlchemy-движок + фабрика сессий.

SQLite настраивается через PRAGMA на каждом новом физическом соединении:
  • journal_mode=WAL        — читатели не блокируются писателем и наоборот;
  • busy_timeout=30000      — вместо мгновенного «database is locked» SQLite
                              ждёт до 30 секунд, повторяя попытку;
  • synchronous=NORMAL      — безопасная пара к WAL, меньше fsync;
  • foreign_keys=ON         — включает FK (по умолчанию в SQLite выключены).

Без этого фоновый поток пайплайна (BackgroundTasks) и обработчики запросов
(FastAPI threadpool) «душат» друг друга: ошибка из лога — именно этот случай.
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

os.makedirs("data", exist_ok=True)

_is_sqlite = settings.database_url.startswith("sqlite")

# Python-уровневый timeout (секунды) — страховка поверх busy_timeout.
# check_same_thread=False нужен, т.к. FastAPI выполняет sync-эндпоинты
# и BackgroundTasks в разных потоках.
_connect_args: dict = {}
if _is_sqlite:
    _connect_args = {
        "check_same_thread": False,
        "timeout": 30,
    }

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        """Выполняется один раз на каждое новое физическое соединение.
        Регистрируется ДО первого подключения, поэтому PRAGMA действуют
        с самого старта приложения."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 сек
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — одна сессия на запрос."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()