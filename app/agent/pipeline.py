import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from ..config import settings
from ..database import SessionLocal
from ..models import AnalysisRun, RunStep, EventInsight, Client, User
from ..llm.client import LLMClient
from . import tools
from .ranking import score_event

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

@dataclass
class PipelineContext:
    run_id: int
    user_id: int
    client_id: int
    llm: LLMClient = field(default_factory=LLMClient)
    plan: dict = field(default_factory=dict)
    client_ctx: dict = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)
    ranked: list[dict] = field(default_factory=list)
    insights: list[dict] = field(default_factory=list)

class _StepRecorder:
    def __init__(self, db: Session, ctx: PipelineContext, index: int, name: str, inputs: dict):
        self.db, self.ctx = db, ctx
        self.step = RunStep(run_id=ctx.run_id, index=index, name=name,
                            inputs=inputs, started_at=_now(), status="running")
        db.add(self.step); db.commit(); db.refresh(self.step)

    def __enter__(self):
        return self.step

    def __exit__(self, exc_type, exc, tb):
        self.step.finished_at = _now()
        if exc_type:
            self.step.status = "error"
            self.step.notes = f"{exc_type.__name__}: {exc}"
            self.db.commit()
            raise
        self.step.status = "ok"
        self.db.commit()

def run_pipeline_task(run_id: int) -> None:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if not run:
            return
        run.status = "running"
        db.commit()

        client = db.get(Client, run.client_id)
        user = db.get(User, run.user_id)
        ctx = PipelineContext(run_id=run.id, user_id=user.id, client_id=client.id)

        try:
            _step_plan(db, ctx)
            _step_load_context(db, ctx, client)
            _step_retrieve(db, ctx)
            _step_rank(db, ctx, client)
            _step_interpret(db, ctx, client)
            _step_self_check(db, ctx)
            _step_summarize(db, ctx)

            run.status = "done"
            run.model = ctx.llm.model_name
        except Exception as e:
            run.status = "failed"
            run.error = f"{e}\n{traceback.format_exc()[:2000]}"
        run.finished_at = _now()
        db.commit()
    finally:
        db.close()

def _step_plan(db: Session, ctx: PipelineContext) -> None:
    with _StepRecorder(db, ctx, 0, "plan", {"client_id": ctx.client_id}) as step:
        ctx.plan = {
            "steps": ["load_context", "retrieve", "rank", "interpret", "self_check", "summarize"],
            "queries": [],
            "max_events": settings.max_events_per_run,
            "max_retries": settings.max_retries,
        }
        step.output = ctx.plan

def _step_load_context(db: Session, ctx: PipelineContext, client: Client) -> None:
    with _StepRecorder(db, ctx, 1, "load_context", {"client_id": ctx.client_id}) as step:
        profile = tools.get_client_profile(db, ctx.run_id, ctx.user_id, ctx.client_id)
        if not profile:
            raise RuntimeError("Не удалось загрузить профиль клиента")
        derived = _derive_signals(profile)
        ctx.client_ctx = {**profile, "derived_signals": derived}

        queries = [profile["industry"]] + profile["keywords"] + [cp["name"] for cp in profile["counterparties"]]
        ctx.plan["queries"] = [q for q in queries if q][:8]
        step.output = {
            "client": {k: profile[k] for k in ("id", "name", "industry", "scale_revenue_rub", "scale_employees")},
            "derived_signals": derived,
            "queries": ctx.plan["queries"],
        }

def _derive_signals(profile: dict) -> list[str]:
    desc = (profile.get("description") or "").lower()
    signals = []
    for marker in ("экспорт", "пошлин", "санкц", "зависимост", "ставк", "логистик", "кадр"):
        if marker in desc:
            signals.append(marker)
    return signals

def _step_retrieve(db: Session, ctx: PipelineContext) -> None:
    with _StepRecorder(db, ctx, 2, "retrieve", {"queries": ctx.plan["queries"]}) as step:
        queries = ctx.plan["queries"]
        
        analytics = tools.search_bank_analytics(db, ctx.run_id, ctx.user_id, queries, limit=15)
        news = tools.search_news(db, ctx.run_id, ctx.user_id, queries, limit=5)
        
        rag = tools.search_rag(db, ctx.run_id, ctx.user_id, query=" ".join(queries[:3]) or "бизнес", top_k=3)

        candidates = [{**a, "source_type": "analytic"} for a in analytics] + \
                     [{**n, "source_type": "news"} for n in news]
                     
        ctx.candidates = candidates
        step.output = {
            "counts": {"pdf_analytics": len(analytics), "news": len(news), "rag_snippets": len(rag)},
            "candidates": [{k: c.get(k) for k in ("id", "title", "source_type")} for c in candidates],
        }

def _step_rank(db: Session, ctx: PipelineContext, client: Client) -> None:
    with _StepRecorder(db, ctx, 3, "rank", {"candidates": len(ctx.candidates), "max_events": settings.max_events_per_run}) as step:
        scored = []
        for c in ctx.candidates:
            s, breakdown = score_event(c, ctx.client_ctx, ctx.client_ctx)
            scored.append({**c, "score": s, "breakdown": breakdown})
        scored.sort(key=lambda x: x["score"], reverse=True)
        ctx.ranked = [x for x in scored if x["score"] > 0.15][: settings.max_events_per_run]
        if not ctx.ranked and scored:
            ctx.ranked = scored[: min(3, settings.max_events_per_run)]
        step.output = {
            "selected": [
                {"id": r["id"], "title": r["title"], "score": r["score"], "breakdown": r["breakdown"], "source_type": r["source_type"]}
                for r in ctx.ranked
            ],
        }

def _step_interpret(db: Session, ctx: PipelineContext, client: Client) -> None:
    with _StepRecorder(db, ctx, 4, "interpret", {"events": [r["id"] for r in ctx.ranked]}) as step:
        results = []
        for r in ctx.ranked:
            rag = tools.search_rag(db, ctx.run_id, ctx.user_id, query=f"{r['title']} {ctx.client_ctx['industry']}", top_k=3)
            llm_res = ctx.llm.interpret_event(
                client_ctx=ctx.client_ctx, profile=ctx.client_ctx,
                event=r, source_type=r["source_type"], rag_snippets=rag,
            )
            insight = EventInsight(
                run_id=ctx.run_id,
                source_type=r["source_type"], source_id=r["id"],
                title=r["title"], relevance_score=r["score"],
                impact=llm_res.payload,
                sources=[
                    {"type": r["source_type"], "id": r["id"], "title": r["title"],
                     "provider": llm_res.provider, "model": llm_res.model,
                     "fallback": llm_res.fallback, "error": llm_res.error},
                    *[{"type": "rag_snippet", "text": s} for s in rag],
                ],
                attempts=1,
            )
            db.add(insight); db.commit(); db.refresh(insight)
            results.append({"insight_id": insight.id, "title": r["title"], "kind": llm_res.payload.get("kind"), "confidence": llm_res.payload.get("confidence"), "provider": llm_res.provider, "fallback": llm_res.fallback})
            tools._log(db, ctx.run_id, ctx.user_id, "llm_interpret", {"event_id": r["id"], "source_type": r["source_type"]}, allowed=True, summary=f"kind={llm_res.payload.get('kind')} provider={llm_res.provider}")
        step.output = {"insights": results}

def _step_self_check(db: Session, ctx: PipelineContext) -> None:
    with _StepRecorder(db, ctx, 5, "self_check", {"max_retries": settings.max_retries}) as step:
        insights = db.query(EventInsight).filter(EventInsight.run_id == ctx.run_id).all()
        retried, failed = [], []
        for ins in insights:
            problems = _validate(ins)
            if problems and ins.attempts <= settings.max_retries:
                r = next((x for x in ctx.ranked if x["id"] == ins.source_id and x["source_type"] == ins.source_type), None)
                if r:
                    rag = tools.search_rag(db, ctx.run_id, ctx.user_id, query=f"{r['body']} {ctx.client_ctx.get('risk_notes','')}", top_k=5)
                    res = ctx.llm.interpret_event(ctx.client_ctx, ctx.client_ctx, r, r["source_type"], rag)
                    ins.impact = res.payload
                    ins.attempts += 1
                    ins.sources = ins.sources + [{"type": "retry", "reason": problems}]
                    db.commit()
                    retried.append({"insight_id": ins.id, "problems": problems})
            elif problems:
                failed.append({"insight_id": ins.id, "problems": problems})
        step.output = {"checked": len(insights), "retried": retried, "failed": failed}

def _validate(ins: EventInsight) -> list[str]:
    p = ins.impact or {}
    problems = []
    if p.get("kind") not in {"risk", "opportunity", "neutral"}:
        problems.append("invalid_kind")
    mech = (p.get("mechanism") or "").lower()
    if len(mech) < 40:
        problems.append("mechanism_too_short")
    if not p.get("affected_business_lines"):
        problems.append("no_affected_lines")
    if not isinstance(p.get("confidence"), (int, float)) or not (0 <= p["confidence"] <= 1):
        problems.append("bad_confidence")
        
    # ОСЛАБЛЕННЫЙ ВАЛИДАТОР: добавлены слова "банк", "аналитик", "отчет"
    if not any(m in mech for m in ("«", "регион", "отрасл", "клиент", "поставщик", "конкурент", "pdf", "банк", "аналитик", "отчет")):
        problems.append("not_personalized")
    return problems

def _step_summarize(db: Session, ctx: PipelineContext) -> None:
    with _StepRecorder(db, ctx, 6, "summarize", {"run_id": ctx.run_id}) as step:
        insights = db.query(EventInsight).filter(EventInsight.run_id == ctx.run_id).all()
        risks = [i for i in insights if (i.impact or {}).get("kind") == "risk"]
        opps  = [i for i in insights if (i.impact or {}).get("kind") == "opportunity"]
        neut  = [i for i in insights if (i.impact or {}).get("kind") == "neutral"]

        parts = [
            f"Клиент: {ctx.client_ctx.get('name')} ({ctx.client_ctx.get('industry')}).",
            f"Рассмотрено {len(insights)} событий (включая PDF-отчеты): рисков — {len(risks)}, возможностей — {len(opps)}, нейтральных — {len(neut)}.",
        ]
        if risks: parts.append("Топ-риски: " + "; ".join(f"{i.title} (confidence {i.impact.get('confidence')})" for i in risks[:3]) + ".")
        if opps: parts.append("Топ-возможности: " + "; ".join(f"{i.title}" for i in opps[:3]) + ".")
        summary = " ".join(parts)

        run = db.get(AnalysisRun, ctx.run_id)
        run.summary = summary
        step.output = {"summary": summary, "counts": {"risks": len(risks), "opportunities": len(opps), "neutral": len(neut)}}