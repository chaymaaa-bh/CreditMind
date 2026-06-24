from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

router = APIRouter(prefix="/graphrag", tags=["graphrag"])

_rag: Any = None
_rag_error: str | None = None


def _get_rag():
    global _rag, _rag_error
    if _rag is not None:
        return _rag
    if _rag_error is not None:
        raise HTTPException(status_code=503, detail=_rag_error)
    try:
        from m6_graphrag.rag_engine import CreditMindRAG
        _rag = CreditMindRAG()
        return _rag
    except Exception as exc:
        _rag_error = f"M6 GraphRAG indisponible : {exc}"
        raise HTTPException(status_code=503, detail=_rag_error)


class QueryRequest(BaseModel):
    question: str


class ConceptRequest(BaseModel):
    concept: str


@router.get("/status")
def get_status() -> dict:
    try:
        _get_rag()
        return {"available": True, "message": "Neo4j + RAG connectés"}
    except HTTPException as e:
        return {"available": False, "message": e.detail}


@router.post("/query")
def natural_language_query(req: QueryRequest) -> dict:
    rag = _get_rag()
    try:
        answer = rag.query(req.question)
        return {"question": req.question, "answer": answer}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/client/{client_id}")
def get_client_report(client_id: str) -> dict:
    rag = _get_rag()
    try:
        report = rag.get_client_report(client_id)
        return {"client_id": client_id, "report": report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/explain")
def explain_concept(req: ConceptRequest) -> dict:
    rag = _get_rag()
    try:
        explanation = rag.explain_concept(req.concept)
        return {"concept": req.concept, "explanation": explanation}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/contagion/{client_id}")
def contagion_analysis(client_id: str, depth: int = 2) -> dict:
    rag = _get_rag()
    try:
        analysis = rag.contagion_analysis(client_id, depth=depth)
        return {"client_id": client_id, "depth": depth, "analysis": analysis}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/portfolio")
def portfolio_overview() -> dict:
    rag = _get_rag()
    try:
        overview = rag.portfolio_overview()
        return {"overview": overview}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/concepts")
def list_concepts() -> list[dict]:
    rag = _get_rag()
    try:
        return rag.list_concepts()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/rules")
def list_rules() -> list[dict]:
    rag = _get_rag()
    try:
        return rag.list_decision_rules()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
