"""Pydantic-схемы ответов API."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str


class ClientProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    products: list = []
    counterparties: list = []
    regions: list = []
    keywords: list = []
    risk_notes: str = ""


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    industry: str
    # Добавлена защита от None (пустых значений в CSV)
    scale_revenue_rub: float | None = 0.0
    scale_employees: int | None = 0
    description: str | None = ""
    profile: ClientProfileOut | None = None


class ClientBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    industry: str
    scale_revenue_rub: float | None = 0.0
    scale_employees: int | None = 0


class ClientListOut(BaseModel):
    items: list[ClientBrief]
    total: int
    page: int
    size: int


class NewsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    body: str
    source: str
    published_at: datetime
    entities: list = []
    industries: list = []
    regions: list = []
    magnitude: float = 0.5


class AnalyticOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    body: str
    category: str
    published_at: datetime
    entities: list = []
    industries: list = []
    regions: list = []


class RunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    index: int
    name: str
    status: str
    inputs: dict[str, Any] = {}
    output: dict[str, Any] = {}
    notes: str = ""
    started_at: datetime
    finished_at: datetime | None = None


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_type: str
    source_id: int
    title: str
    relevance_score: float
    impact: dict[str, Any] = {}
    sources: list = []
    attempts: int = 1


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    user_id: int
    status: str
    model: str
    summary: str
    error: str
    created_at: datetime
    finished_at: datetime | None = None


class RunDetail(RunOut):
    steps: list[RunStepOut] = []
    insights: list[InsightOut] = []


class ToolLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int | None
    tool: str
    params: dict[str, Any] = {}
    result_summary: str
    allowed: bool
    reason: str
    created_at: datetime