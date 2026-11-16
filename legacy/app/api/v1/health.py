from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/api/v1")

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0-analyst"
    }
