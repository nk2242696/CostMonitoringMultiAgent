"""
Chat & Architecture Review API Endpoints

Preserved from existing implementation, cleaned up and moved into a router.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_agent_runtime, get_api_key_owner, get_db, get_request_id
from src.agents.runtime import AgentRuntime, AgentRuntimeUnavailable
from src.common.config import get_config
from src.common.database import get_database, get_session
from src.monitoring.recommendations.multi_agent_system import MultiAgentSystem

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat & Reviews"])


# ── Schemas ──


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime
    agents_involved: Optional[List[str]] = None
    run_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    usage: Dict[str, int] = Field(default_factory=dict)
    ai_generated: bool = False


class ArchitectureReviewRequest(BaseModel):
    problem_statement: str
    review_id: Optional[str] = None


# ── Chat ──


@router.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_api_key_owner),
    request_id: str = Depends(get_request_id),
):
    """Chat with AI agents about cost analysis."""
    try:
        config = get_config()
        session_id = payload.session_id or str(uuid.uuid4())
        if config.agents.agent_runtime_enabled:
            runtime = AgentRuntime(
                db, config.agents, config.workspace,
                checkpointer=getattr(http_request.app.state, "agent_checkpointer", None),
            )
            result = await runtime.run_chat(
                payload.message, thread_id=session_id, actor_id=actor_id,
                request_id=request_id,
            )
            return ChatResponse(
                response=result.get("final_response", {}).get("answer", ""),
                session_id=session_id,
                timestamp=datetime.now(timezone.utc),
                agents_involved=result.get("selected_personas", []),
                run_id=result.get("run_id"),
                evidence_ids=[item["evidence_id"] for item in result.get("evidence", [])],
                usage=result.get("usage", {}),
                ai_generated=True,
            )

        agent_system = MultiAgentSystem(db_session=db)
        response_text = await agent_system.query(payload.message)

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            agents_involved=None,
            ai_generated=not agent_system.fallback_only,
        )
    except AgentRuntimeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Chat error: %s", exc, exc_info=True)
        raise HTTPException(500, "Chat request failed safely") from exc


@router.post("/api/v2/chat", response_model=ChatResponse)
async def agent_chat(
    payload: ChatRequest,
    runtime: AgentRuntime = Depends(get_agent_runtime),
    actor_id: str = Depends(get_api_key_owner),
    request_id: str = Depends(get_request_id),
):
    """Run the durable LangGraph chat workflow when explicitly enabled."""
    thread_id = payload.session_id or str(uuid.uuid4())
    try:
        result = await runtime.run_chat(
            payload.message,
            thread_id=thread_id,
            actor_id=actor_id,
            request_id=request_id,
        )
    except AgentRuntimeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent chat failed")
        raise HTTPException(status_code=502, detail="Agent workflow failed safely") from exc

    return ChatResponse(
        response=result.get("final_response", {}).get("answer", ""),
        session_id=thread_id,
        timestamp=datetime.now(timezone.utc),
        agents_involved=result.get("selected_personas", []),
        run_id=result.get("run_id"),
        evidence_ids=[item["evidence_id"] for item in result.get("evidence", [])],
        usage=result.get("usage", {}),
        ai_generated=True,
    )


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    db_context = get_database().get_session()
    db = db_context.__enter__()

    try:
        config = get_config()
        agent_system = MultiAgentSystem(db_session=db)
        runtime = AgentRuntime(
            db, config.agents, config.workspace,
            checkpointer=getattr(websocket.app.state, "agent_checkpointer", None),
        )
        thread_id = str(uuid.uuid4())

        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            if not user_message:
                await websocket.send_json({"error": "Empty message"})
                continue

            await websocket.send_json({"status": "thinking", "message": "Analysing..."})

            try:
                if config.agents.agent_runtime_enabled:
                    result = await runtime.run_chat(
                        user_message, thread_id=thread_id, actor_id="websocket",
                        request_id=str(uuid.uuid4()),
                    )
                    response = result.get("final_response", {}).get("answer", "")
                else:
                    response = await agent_system.query(user_message)
                await websocket.send_json(
                    {"status": "complete", "response": response, "timestamp": datetime.now(timezone.utc).isoformat()}
                )
            except Exception as qe:
                await websocket.send_json({"status": "error", "error": str(qe)})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        db_context.__exit__(None, None, None)


@router.get("/api/v1/chat/suggestions")
async def chat_suggestions():
    return [
        {
            "category": "Cost Analysis",
            "questions": [
                "What's my total cloud spend this month?",
                "Show me cost breakdown by service",
                "Which services had the biggest cost increase?",
            ],
        },
        {
            "category": "Budget & Forecasting",
            "questions": [
                "Are we over budget this month?",
                "What's the forecast for next month?",
            ],
        },
        {
            "category": "Optimization",
            "questions": [
                "How can I reduce costs by 10%?",
                "What are the top cost optimization opportunities?",
            ],
        },
    ]


# ── Architecture Review ──


@router.post("/api/v1/architecture/review")
async def run_architecture_review(
    request: ArchitectureReviewRequest,
    db: Session = Depends(get_session),
):
    """Run 3-agent architecture review (Tier 1)."""
    from src.recommendations.architecture_reviewer import ArchitectureRecommender

    recommender = ArchitectureRecommender(db)
    result = recommender.run_architecture_review(
        request.problem_statement, request.review_id
    )
    return {**result, "generated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/api/v1/architecture/reviews")
async def list_reviews(db: Session = Depends(get_session)):
    from src.models import ArchitectureReview

    reviews = db.query(ArchitectureReview).order_by(ArchitectureReview.created_at.desc()).all()
    return {
        "reviews": [
            {
                "review_id": r.review_id,
                "decision_status": r.decision_status,
                "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) is not None else None,
                "summary_preview": (r.summary or "")[:300],
            }
            for r in reviews
        ],
        "count": len(reviews),
    }
