import re
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import MLStats
from ..schemas import MLStatsOut, MLLearnIn

router = APIRouter()


def _get_or_create_ml(db: DBSession) -> MLStats:
    ml = db.query(MLStats).filter(MLStats.id == 1).first()
    if not ml:
        ml = MLStats(id=1, patterns={}, log=[])
        db.add(ml)
        db.commit()
        db.refresh(ml)
    return ml


@router.get("/ml/stats", response_model=MLStatsOut)
def get_ml_stats(db: DBSession = Depends(get_db)):
    ml = _get_or_create_ml(db)
    return MLStatsOut(
        total_sessions=ml.total_sessions or 0,
        total_processed=ml.total_processed or 0,
        total_valid=ml.total_valid or 0,
        fixes_comma=ml.fixes_comma or 0,
        fixes_emoji=ml.fixes_emoji or 0,
        fixes_dup=ml.fixes_dup or 0,
        fixes_fix55=ml.fixes_fix55 or 0,
        fixes_header=ml.fixes_header or 0,
        patterns=ml.patterns or {},
        log=ml.log or [],
    )


@router.post("/ml/learn")
def ml_learn(data: MLLearnIn, db: DBSession = Depends(get_db)):
    """Endpoint para o frontend atualizar dados de aprendizado manualmente."""
    ml = _get_or_create_ml(db)

    ml.total_sessions = (ml.total_sessions or 0) + 1
    ml.total_processed = (ml.total_processed or 0) + data.total
    ml.total_valid = (ml.total_valid or 0) + data.valid
    ml.fixes_comma = (ml.fixes_comma or 0) + data.fixed_comma
    ml.fixes_emoji = (ml.fixes_emoji or 0) + data.fixed_emoji
    ml.fixes_dup = (ml.fixes_dup or 0) + data.dups
    ml.fixes_fix55 = (ml.fixes_fix55 or 0) + data.fix55
    if data.had_header:
        ml.fixes_header = (ml.fixes_header or 0) + 1

    patterns = dict(ml.patterns or {})
    for num in data.sample_numbers:
        d = re.sub(r"\D", "", num)
        if 10 <= len(d) <= 13:
            prefix = d[:4]
            patterns[prefix] = patterns.get(prefix, 0) + 1
    ml.patterns = patterns

    log = list(ml.log or [])
    if data.msg:
        log.insert(0, {"date": datetime.utcnow().isoformat(), "msg": data.msg})
        ml.log = log[:50]

    db.commit()
    return {"ok": True}


@router.delete("/ml/reset")
def ml_reset(db: DBSession = Depends(get_db)):
    """Zera os dados de aprendizado."""
    ml = _get_or_create_ml(db)
    ml.total_sessions = 0
    ml.total_processed = 0
    ml.total_valid = 0
    ml.fixes_comma = 0
    ml.fixes_emoji = 0
    ml.fixes_dup = 0
    ml.fixes_fix55 = 0
    ml.fixes_header = 0
    ml.patterns = {}
    ml.log = []
    db.commit()
    return {"ok": True}
