"""
FastAPI main application for Azure Cost Monitoring.
"""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from src.common.database import get_session, init_db, get_database
from src.monitoring.storage.models import (
    AIRecommendation,
    CostRecord,
    CostAggregation,
    CostBudget,
    Anomaly,
)
from src.monitoring.recommendations.multi_agent_system import MultiAgentSystem
from src.monitoring.recommendations.architecture_review_service import ArchitectureReviewService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create FastAPI application
app = FastAPI(
    title="Azure Cost Monitoring API",
    description="Real-time cost monitoring, AI recommendations, and optimization for Azure resources",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("API starting up...")

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API responses
class RecommendationResponse(BaseModel):
    id: int
    generated_at: datetime
    service_name: str
    current_cost: float
    potential_savings: float
    savings_percentage: Optional[float]
    title: str
    recommendation_text: str
    priority: str
    category: str
    implementation_effort: Optional[str]
    source: str
    status: str

    class Config:
        from_attributes = True


class CostSummaryResponse(BaseModel):
    total_cost: float
    resource_count: int
    top_services: List[dict]
    trend: str


class RecommendationSummaryResponse(BaseModel):
    total_recommendations: int
    total_potential_savings: float
    high_priority: int
    medium_priority: int
    low_priority: int
    by_status: dict
    by_category: dict


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


class ArchitectureReviewResponse(BaseModel):
    review_id: str
    proposal: str
    review: str
    decision: str
    summary: str
    files: Dict[str, str]
    generated_at: datetime


# Initialize multi-agent system (lazy loading)
_agent_system = None
_architecture_review_service = None

def get_agent_system(session: Session = Depends(get_session)) -> MultiAgentSystem:
    """Get or create multi-agent system instance"""
    global _agent_system
    if _agent_system is None:
        azure_openai_key = os.getenv("AZURE_OPENAI_KEY")
        azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        
        if not azure_openai_key or not azure_openai_endpoint:
            raise HTTPException(
                status_code=500,
                detail="Azure OpenAI credentials not configured"
            )
        
        _agent_system = MultiAgentSystem(azure_openai_key, azure_openai_endpoint, session)
    return _agent_system


def get_architecture_review_service() -> ArchitectureReviewService:
    """Get or create architecture review service instance"""
    global _architecture_review_service
    if _architecture_review_service is None:
        _architecture_review_service = ArchitectureReviewService()
    return _architecture_review_service


# Health check endpoint
@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with database and service status."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "azure-cost-monitoring-api",
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check database connectivity
    try:
        db = next(get_session())
        # Simple query to verify connection
        db.execute(func.now())
        db.close()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "PostgreSQL connection successful"
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
    
    # Check if we have recent data (collected in last 24 hours)
    try:
        db = next(get_session())
        recent_data = db.query(CostRecord).filter(
            CostRecord.created_at >= datetime.utcnow() - timedelta(days=1)
        ).first()
        db.close()
        
        if recent_data:
            health_status["checks"]["data_freshness"] = {
                "status": "healthy",
                "message": "Recent cost data available"
            }
        else:
            health_status["status"] = "degraded"
            health_status["checks"]["data_freshness"] = {
                "status": "warning",
                "message": "No cost data collected in last 24 hours"
            }
    except Exception as e:
        health_status["checks"]["data_freshness"] = {
            "status": "unknown",
            "message": f"Unable to check data freshness: {str(e)}"
        }
    
    return health_status


@app.get("/health/ready")
async def readiness_check():
    """Readiness check for Kubernetes/container orchestration."""
    try:
        db = next(get_session())
        db.execute(func.now())
        db.close()
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes/container orchestration."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


# Cost endpoints
@app.get("/api/costs/summary")
def get_cost_summary(
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session),
):
    """Get cost summary for the specified period."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Total cost
        total_cost = session.query(func.sum(CostRecord.cost)).filter(
            CostRecord.date >= start_date
        ).scalar() or 0.0
        
        # Resource count (using service_name + subscription_id as unique resource)
        resource_count = session.query(
            func.count(func.distinct(CostRecord.service_name + '_' + CostRecord.subscription_id))
        ).filter(
            CostRecord.date >= start_date
        ).scalar() or 0
        
        # Top services
        top_services_query = session.query(
            CostRecord.service_name,
            func.sum(CostRecord.cost).label("total_cost")
        ).filter(
            CostRecord.date >= start_date
        ).group_by(CostRecord.service_name).order_by(desc("total_cost")).limit(5)
        
        top_services = [
            {"service": row.service_name, "cost": float(row.total_cost)}
            for row in top_services_query.all()
        ]
        
        return CostSummaryResponse(
            total_cost=float(total_cost),
            resource_count=resource_count,
            top_services=top_services,
            trend="stable"  # TODO: Calculate actual trend
        )
    except Exception as e:
        logger.error(f"Error fetching cost summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AI Recommendation endpoints
@app.get("/api/recommendations", response_model=List[RecommendationResponse])
def get_recommendations(
    limit: int = Query(default=10, ge=1, le=100),
    priority: Optional[str] = Query(default=None, regex="^(high|medium|low)$"),
    status: Optional[str] = Query(default=None, regex="^(pending|approved|rejected|implemented|dismissed)$"),
    service_name: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    Get AI cost recommendations.
    
    - **limit**: Maximum number of recommendations to return (1-100)
    - **priority**: Filter by priority (high, medium, low)
    - **status**: Filter by status (pending, approved, rejected, implemented, dismissed)
    - **service_name**: Filter by service name
    """
    try:
        query = session.query(AIRecommendation).order_by(
            desc(AIRecommendation.potential_savings),
            desc(AIRecommendation.generated_at)
        )
        
        # Apply filters
        if priority:
            query = query.filter(AIRecommendation.priority == priority)
        if status:
            query = query.filter(AIRecommendation.status == status)
        if service_name:
            query = query.filter(AIRecommendation.service_name == service_name)
        
        recommendations = query.limit(limit).all()
        
        return [
            RecommendationResponse(
                id=rec.id,
                generated_at=rec.generated_at,
                service_name=rec.service_name,
                current_cost=float(rec.current_cost) if rec.current_cost else 0.0,
                potential_savings=float(rec.potential_savings) if rec.potential_savings else 0.0,
                savings_percentage=float(rec.savings_percentage) if rec.savings_percentage else None,
                title=rec.title,
                recommendation_text=rec.recommendation_text or rec.recommendation or rec.description or "",
                priority=rec.priority or "medium",
                category=rec.category or "optimization",
                implementation_effort=rec.implementation_effort,
                source=rec.source or "unknown",
                status=rec.status or "pending",
            )
            for rec in recommendations
        ]
    except Exception as e:
        logger.error(f"Error fetching recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations/summary", response_model=RecommendationSummaryResponse)
def get_recommendations_summary(session: Session = Depends(get_session)):
    """Get summary statistics for AI recommendations."""
    try:
        # Total count and savings
        row = session.query(
            func.count(AIRecommendation.id),
            func.sum(AIRecommendation.potential_savings)
        ).one()
        total_recommendations = row[0] or 0
        total_savings = float(row[1] or 0.0)
        
        # Count by priority
        priority_query = session.query(
            AIRecommendation.priority,
            func.count(AIRecommendation.id)
        ).group_by(AIRecommendation.priority)
        priority_counts = {row[0]: row[1] for row in priority_query.all()}
        
        # Count by status
        status_query = session.query(
            AIRecommendation.status,
            func.count(AIRecommendation.id)
        ).group_by(AIRecommendation.status)
        status_counts = {row[0]: row[1] for row in status_query.all()}
        
        # Count by category
        category_query = session.query(
            AIRecommendation.category,
            func.count(AIRecommendation.id)
        ).group_by(AIRecommendation.category)
        category_counts = {row[0]: row[1] for row in category_query.all()}
        
        return RecommendationSummaryResponse(
            total_recommendations=total_recommendations,
            total_potential_savings=total_savings,
            high_priority=priority_counts.get("high", 0),
            medium_priority=priority_counts.get("medium", 0),
            low_priority=priority_counts.get("low", 0),
            by_status=status_counts,
            by_category=category_counts,
        )
    except Exception as e:
        logger.error(f"Error fetching recommendations summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/recommendations/{recommendation_id}/status")
def update_recommendation_status(
    recommendation_id: int,
    status: str = Query(..., regex="^(approved|rejected|implemented|dismissed)$"),
    notes: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Update the status of a recommendation."""
    try:
        recommendation = session.query(AIRecommendation).filter(
            AIRecommendation.id == recommendation_id
        ).first()
        
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        recommendation.status = status
        if notes:
            recommendation.notes = notes
        if status == "implemented":
            recommendation.implemented_at = datetime.utcnow()
        
        session.commit()
        
        return {"message": "Status updated successfully", "id": recommendation_id, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating recommendation status: {e}")
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# Chat endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """
    Chat with AI agents about cost analysis.
    
    Example queries:
    - "Why did costs spike last week?"
    - "Are we over budget this month?"
    - "What can I do to reduce costs?"
    - "Show me the top 5 most expensive services"
    """
    try:
        # Always use fallback-only mode since Azure OpenAI is unreachable
        # Initialize with None to skip Azure OpenAI entirely
        agent_system = MultiAgentSystem(
            azure_openai_key=None,
            azure_openai_endpoint=None,
            db_session=session
        )
        
        # Process query
        response_text = await agent_system.query(request.message)
        
        # Generate session ID if not provided
        import uuid
        session_id = request.session_id or str(uuid.uuid4())
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            timestamp=datetime.utcnow(),
            agents_involved=["orchestrator", "data_analyst", "budget_advisor", "optimizer"]
        )
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        error_msg = str(e)
        
        # Provide detailed error messages with solutions
        if "Connection error" in error_msg or "timeout" in error_msg.lower() or "Name or service not known" in error_msg:
            error_msg = (
                "🚫 Cannot connect to Azure OpenAI endpoint.\n\n"
                "This is likely due to:\n"
                "1. Network restrictions on the Azure OpenAI resource\n"
                "2. Firewall blocking Docker container access\n\n"
                "Solutions:\n"
                "• Add your public IP to Azure OpenAI firewall rules\n"
                "• Enable 'Allow Azure services' in Azure OpenAI networking\n"
                "• Run the API outside Docker (python src/monitoring/api/main.py)\n\n"
                "The chat system is ready - just needs network access configured."
            )
        elif "Unauthorized" in error_msg or "401" in error_msg:
            error_msg = "Azure OpenAI credentials invalid. Please check API key and endpoint configuration."
        
        raise HTTPException(status_code=500, detail=error_msg)


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat with AI agents.
    Provides streaming responses for better UX.
    """
    await websocket.accept()
    
    try:
        # Get database session
        db = next(get_session())
        
        # Initialize agent system with env-var credentials
        agent_system = MultiAgentSystem(
            azure_openai_key=os.getenv("AZURE_OPENAI_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            db_session=db
        )
        
        while True:
            # Receive message
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            
            if not user_message:
                await websocket.send_json({
                    "error": "Empty message",
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue
            
            # Send "thinking" status
            await websocket.send_json({
                "status": "thinking",
                "message": "Analyzing your query with AI agents...",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Process with agents
            try:
                response = await agent_system.query(user_message)
                
                # Send response
                await websocket.send_json({
                    "status": "complete",
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as query_error:
                error_msg = str(query_error)
                if "Connection error" in error_msg or "timeout" in error_msg.lower() or "Name or service not known" in error_msg:
                    error_msg = (
                        "🚫 Cannot connect to Azure OpenAI.\n\n"
                        "Solutions:\n"
                        "1. Add your IP to Azure OpenAI firewall\n"
                        "2. Enable 'Allow Azure services' in networking\n"
                        "3. Run API outside Docker for testing"
                    )
                
                await websocket.send_json({
                    "status": "error",
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
    finally:
        db.close()


@app.get("/chat/suggestions")
async def get_chat_suggestions():
    """
    Get suggested questions for the chat interface.
    Helps users discover what they can ask.
    """
    suggestions = [
        {
            "category": "Cost Analysis",
            "questions": [
                "What's my total cloud spend this month?",
                "Show me cost breakdown by service",
                "Which services had the biggest cost increase?",
                "Compare costs: this month vs last month"
            ]
        },
        {
            "category": "Budget & Forecasting",
            "questions": [
                "Are we over budget this month?",
                "How much budget do we have left?",
                "What's the forecast for next month?",
                "Will we exceed budget by month end?"
            ]
        },
        {
            "category": "Optimization",
            "questions": [
                "How can I reduce costs by 10%?",
                "What are the top cost optimization opportunities?",
                "Show me idle resources I can shut down",
                "Which VMs should I right-size?"
            ]
        },
        {
            "category": "Anomaly Detection",
            "questions": [
                "Why did costs spike yesterday?",
                "Are there any unusual spending patterns?",
                "Which service has abnormal costs?",
                "Explain the cost anomaly on November 15th"
            ]
        },
        {
            "category": "Reporting",
            "questions": [
                "Generate executive cost summary",
                "Show me department-wise cost allocation",
                "What are the cost trends over last 3 months?",
                "Give me a cost report for the finance team"
            ]
        }
    ]
    
    return suggestions


@app.get("/chat/widget")
async def get_chat_widget():
    """
    Serve the chat widget HTML page.
    Can be embedded in Grafana or other dashboards.
    """
    static_path = Path(__file__).parent / "static" / "chat_widget.html"
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="Chat widget not found")
    return FileResponse(static_path)


# ============================================================================
# Architecture Review Endpoints
# ============================================================================

@app.post("/architecture/review", response_model=ArchitectureReviewResponse)
async def run_architecture_review(
    request: ArchitectureReviewRequest,
    service: ArchitectureReviewService = Depends(get_architecture_review_service)
):
    """
    Run a three-agent architecture review for Azure solutions.
    
    This endpoint runs a comprehensive architecture review with:
    - Agent 1: Azure Architecture Proposal
    - Agent 2: Effort/Complexity/Timeline Assessment
    - Agent 3: Final Approval Decision
    
    Example problem_statement:
    ```
    We need to migrate our cost monitoring system to Azure.
    Current: 10 subscriptions, PostgreSQL, Docker
    Requirements: Scale to 50+ subscriptions, support 100+ users
    Budget: $2000-3000/month
    Timeline: 3 months
    Team: 2 engineers
    ```
    """
    try:
        result = service.run_architecture_review(
            request.problem_statement,
            request.review_id
        )
        
        return ArchitectureReviewResponse(
            review_id=result["review_id"],
            proposal=result["proposal"],
            review=result["review"],
            decision=result["decision"],
            summary=result["summary"],
            files=result["files"],
            generated_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"Architecture review failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Architecture review failed: {str(e)}")


@app.get("/architecture/reviews")
async def list_architecture_reviews():
    """List all architecture reviews"""
    review_dir = Path("./architecture_review")
    if not review_dir.exists():
        return {"reviews": []}
    
    reviews = []
    summary_files = list(review_dir.glob("*_00_SUMMARY.md"))
    
    for summary_file in sorted(summary_files, reverse=True):
        review_id = summary_file.stem.replace("_00_SUMMARY", "")
        
        # Extract first few lines for preview
        with open(summary_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            preview = "".join(lines[:10])
        
        reviews.append({
            "review_id": review_id,
            "summary_file": str(summary_file),
            "preview": preview,
            "created_at": datetime.fromtimestamp(summary_file.stat().st_ctime).isoformat()
        })
    
    return {"reviews": reviews, "count": len(reviews)}


@app.get("/architecture/review/{review_id}")
async def get_architecture_review(review_id: str):
    """Get a specific architecture review by ID"""
    review_dir = Path("./architecture_review")
    summary_file = review_dir / f"{review_id}_00_SUMMARY.md"
    
    if not summary_file.exists():
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = f.read()
    
    # Load other files if they exist
    proposal_file = review_dir / f"{review_id}_01_PROPOSAL.md"
    review_file = review_dir / f"{review_id}_02_REVIEW.md"
    decision_file = review_dir / f"{review_id}_03_DECISION.md"
    
    result = {
        "review_id": review_id,
        "summary": summary,
        "files": {
            "summary": str(summary_file)
        }
    }
    
    if proposal_file.exists():
        with open(proposal_file, "r", encoding="utf-8") as f:
            result["proposal"] = f.read()
            result["files"]["proposal"] = str(proposal_file)
    
    if review_file.exists():
        with open(review_file, "r", encoding="utf-8") as f:
            result["review"] = f.read()
            result["files"]["review"] = str(review_file)
    
    if decision_file.exists():
        with open(decision_file, "r", encoding="utf-8") as f:
            result["decision"] = f.read()
            result["files"]["decision"] = str(decision_file)
    
    return result


@app.get("/architecture/review/{review_id}/download/{file_type}")
async def download_review_file(review_id: str, file_type: str):
    """Download a specific review file (summary, proposal, review, or decision)"""
    review_dir = Path("./architecture_review")
    
    file_map = {
        "summary": f"{review_id}_00_SUMMARY.md",
        "proposal": f"{review_id}_01_PROPOSAL.md",
        "review": f"{review_id}_02_REVIEW.md",
        "decision": f"{review_id}_03_DECISION.md"
    }
    
    if file_type not in file_map:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_path = review_dir / file_map[file_type]
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_type}")
    
    return FileResponse(
        file_path,
        media_type="text/markdown",
        filename=file_map[file_type]
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
