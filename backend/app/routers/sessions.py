from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Session, SessionContact
from ..schemas import SessionSummary, SessionDetail, ContactResult
from ..services.storage import load_zip, delete_zip

router = APIRouter()


@router.get("/sessions", response_model=List[SessionSummary])
def list_sessions(
    skip: int = 0,
    limit: int = 50,
    db: DBSession = Depends(get_db),
):
    sessions = db.query(Session).order_by(Session.created_at.desc()).offset(skip).limit(limit).all()
    result = []
    for s in sessions:
        chunks = (s.total_valid + s.total_warn + s.chunk_size - 1) // s.chunk_size if s.chunk_size else 0
        result.append(SessionSummary(
            id=s.id,
            created_at=s.created_at,
            filenames=s.filenames or [],
            total_raw=s.total_raw,
            total_valid=s.total_valid,
            total_warn=s.total_warn,
            total_err=s.total_err,
            duplicates_removed=s.duplicates_removed,
            duplicates_global=s.duplicates_global,
            chunks=chunks,
            status=s.status,
        ))
    return result


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    sc_list = (
        db.query(SessionContact)
        .filter(SessionContact.session_id == session_id)
        .all()
    )
    contacts = [
        ContactResult(
            nome=sc.raw_name or "",
            numero=sc.raw_number or "",
            status=sc.status or "err",
            issues=[],
            file=session.filenames[0] if session.filenames else "",
        )
        for sc in sc_list
    ]

    chunks = (session.total_valid + session.total_warn + session.chunk_size - 1) // session.chunk_size if session.chunk_size else 0

    return SessionDetail(
        id=session.id,
        created_at=session.created_at,
        filenames=session.filenames or [],
        total_raw=session.total_raw,
        total_valid=session.total_valid,
        total_warn=session.total_warn,
        total_err=session.total_err,
        duplicates_removed=session.duplicates_removed,
        duplicates_global=session.duplicates_global,
        fixes=session.fixes or {},
        chunks=chunks,
        status=session.status,
        contacts=contacts,
    )


@router.get("/sessions/{session_id}/download")
def download_session_zip(session_id: int, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    if not session.zip_path:
        raise HTTPException(status_code=404, detail="ZIP não disponível para esta sessão")

    try:
        zip_bytes = load_zip(session.zip_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo ZIP não encontrado no servidor")

    from datetime import datetime
    date_str = session.created_at.strftime("%Y-%m-%d")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=Contatos_{date_str}.zip"},
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.zip_path:
        delete_zip(session.zip_path)

    db.delete(session)
    db.commit()
    return {"ok": True, "deleted_id": session_id}
