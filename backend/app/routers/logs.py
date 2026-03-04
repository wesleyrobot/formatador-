"""
Monitoramento: health check completo + log de erros HTTP.
"""
import os
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import SessionLocal, engine
from ..models import ErrorLog

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health/full")
async def health_full(db: Session = Depends(get_db)):
    """Health check completo: banco + Gemini API."""
    result = {"status": "ok", "checks": {}, "timestamp": datetime.utcnow().isoformat()}

    # Banco de dados
    try:
        db.execute(text("SELECT 1"))
        result["checks"]["database"] = {"status": "ok"}
    except Exception as e:
        result["checks"]["database"] = {"status": "error", "detail": str(e)}
        result["status"] = "degraded"

    # Gemini API
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        result["checks"]["gemini"] = {"status": "error", "detail": "GEMINI_API_KEY não configurada"}
        result["status"] = "degraded"
    else:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
            if resp.status_code == 200:
                result["checks"]["gemini"] = {"status": "ok"}
            else:
                result["checks"]["gemini"] = {"status": "error", "detail": f"HTTP {resp.status_code}"}
                result["status"] = "degraded"
        except Exception as e:
            result["checks"]["gemini"] = {"status": "error", "detail": str(e)}
            result["status"] = "degraded"

    # Erros recentes (últimas 24h)
    try:
        from sqlalchemy import func
        count = db.query(func.count(ErrorLog.id)).scalar()
        result["checks"]["error_count_total"] = count
    except Exception:
        result["checks"]["error_count_total"] = "N/A"

    return result


@router.get("/logs")
def list_logs(limit: int = 50, db: Session = Depends(get_db)):
    """Lista os erros HTTP mais recentes."""
    logs = (
        db.query(ErrorLog)
        .order_by(ErrorLog.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [
        {
            "id": l.id,
            "created_at": l.created_at.isoformat(),
            "method": l.method,
            "endpoint": l.endpoint,
            "status_code": l.status_code,
            "error_message": l.error_message,
        }
        for l in logs
    ]


@router.delete("/logs")
def clear_logs(db: Session = Depends(get_db)):
    """Limpa todos os logs de erro."""
    deleted = db.query(ErrorLog).delete()
    db.commit()
    return {"deleted": deleted}
