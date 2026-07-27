"""
Chat & Architecture Review API Endpoints

Preserved from existing implementation, cleaned up and moved into a router.
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.common.database import get_session
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


class ArchitectureReviewRequest(BaseModel):
    problem_statement: str
    review_id: Optional[str] = None


# ── Chat ──


@router.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_session)):
    """Chat with AI agents about cost analysis."""
    try:
        agent_system = MultiAgentSystem(
            azure_openai_key=os.getenv("AZURE_OPENAI_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            db_session=db,
        )
        response_text = await agent_system.query(request.message)
        session_id = request.session_id or str(uuid.uuid4())

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            timestamp=datetime.utcnow(),
            agents_involved=None,
        )
    except Exception as exc:
        logger.error("Chat error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    db = next(get_session())

    try:
        agent_system = MultiAgentSystem(
            azure_openai_key=os.getenv("AZURE_OPENAI_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            db_session=db,
        )

        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            if not user_message:
                await websocket.send_json({"error": "Empty message"})
                continue

            await websocket.send_json({"status": "thinking", "message": "Analysing..."})

            try:
                response = await agent_system.query(user_message)
                await websocket.send_json(
                    {"status": "complete", "response": response, "timestamp": datetime.utcnow().isoformat()}
                )
            except Exception as qe:
                await websocket.send_json({"status": "error", "error": str(qe)})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        db.close()


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
    return {**result, "generated_at": datetime.utcnow().isoformat()}


@router.get("/api/v1/architecture/reviews")
async def list_reviews(db: Session = Depends(get_session)):
    from src.models import ArchitectureReview

    reviews = db.query(ArchitectureReview).order_by(ArchitectureReview.created_at.desc()).all()
    return {
        "reviews": [
            {
                "review_id": r.review_id,
                "decision_status": r.decision_status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "summary_preview": (r.summary or "")[:300],
            }
            for r in reviews
        ],
        "count": len(reviews),
    }
