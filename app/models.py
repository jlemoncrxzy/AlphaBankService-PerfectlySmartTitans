"""ORM-модели. Все «сырые» и производные сущности, участвующие в трассировке."""
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")  # viewer|analyst|admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class Client(Base):
    """Крупный бизнес-клиент банка."""
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    industry: Mapped[str] = mapped_column(String(128))
    scale_revenue_rub: Mapped[float] = mapped_column(Float, default=0.0)
    scale_employees: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    profile: Mapped["ClientProfile"] = relationship(
        back_populates="client", uselist=False, cascade="all, delete-orphan"
    )


class ClientProfile(Base):
    """Бизнес-контекст, «автоматически определяемый» из синтетических данных.
    В MVP — нормализуется пайплайном (шаг load_context) + лёгкое обогащение
    из description (см. pipeline._derive_signals)."""
    __tablename__ = "client_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), unique=True)
    products: Mapped[list] = mapped_column(JSON, default=list)        # [str]
    counterparties: Mapped[list] = mapped_column(JSON, default=list)  # [{name, role, share}]
    regions: Mapped[list] = mapped_column(JSON, default=list)         # [str]
    keywords: Mapped[list] = mapped_column(JSON, default=list)        # [str]
    risk_notes: Mapped[str] = mapped_column(Text, default="")
    client: Mapped[Client] = relationship(back_populates="profile")


class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(128), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    entities: Mapped[list] = mapped_column(JSON, default=list)    # [str] — компании/персоны
    industries: Mapped[list] = mapped_column(JSON, default=list)  # [str]
    regions: Mapped[list] = mapped_column(JSON, default=list)     # [str]
    magnitude: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1 значимость
    url: Mapped[str] = mapped_column(String(512), default="")


class BankAnalytic(Base):
    """Аналитические материалы Альфа-Банка (смоделированные)."""
    __tablename__ = "bank_analytics"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    industries: Mapped[list] = mapped_column(JSON, default=list)
    regions: Mapped[list] = mapped_column(JSON, default=list)
    magnitude: Mapped[float] = mapped_column(Float, default=0.5)


class AnalysisRun(Base):
    """Один запуск агента по клиенту."""
    __tablename__ = "analysis_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|done|failed
    model: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    steps: Mapped[list["RunStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunStep.index"
    )
    insights: Mapped[list["EventInsight"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunStep(Base):
    """Трассировка одного шага пайплайна: что на входе, что на выходе, сколько заняло."""
    __tablename__ = "run_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"))
    index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="ok")
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    run: Mapped[AnalysisRun] = relationship(back_populates="steps")


class EventInsight(Base):
    """Персонализированный вывод по событию (риск/возможность + механизм)."""
    __tablename__ = "event_insights"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"))
    source_type: Mapped[str] = mapped_column(String(16))  # news|analytic
    source_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(512))
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    impact: Mapped[dict] = mapped_column(JSON, default=dict)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    run: Mapped[AnalysisRun] = relationship(back_populates="insights")


class ToolLog(Base):
    """Журнал обращений к инструментам. Для каждого вызова: разрешён/нет, параметры, результат."""
    __tablename__ = "tool_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tool: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[str] = mapped_column(String(512), default="")
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

class DocumentChunk(Base):
    """Кусок текста из PDF-аналитики Альфа-Банка для RAG."""
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), default="")
    industries: Mapped[list] = mapped_column(JSON, default=list)
    text: Mapped[str] = mapped_column(Text)