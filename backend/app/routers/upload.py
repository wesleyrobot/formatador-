import re
from typing import List
from fastapi import APIRouter, UploadFile, File, Depends, Form
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Session, Contact, SessionContact, MLStats
from ..schemas import UploadResponse, ContactResult
from ..services.file_parser import parse_file
from ..services.processor import process_rows, deduplicate, split_chunks, generate_zip
from ..services.storage import save_zip

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    emoji: bool = Form(True),
    dup: bool = Form(True),
    val: bool = Form(True),
    fix55: bool = Form(True),
    fixc: bool = Form(True),
    chunk_size: int = Form(49),
    db: DBSession = Depends(get_db),
):
    opts = {"emoji": emoji, "dup": dup, "val": val, "fix55": fix55, "fixc": fixc}

    all_contacts = []
    filenames = []
    combined_fixes = {"comma": 0, "emoji": 0, "dup": 0, "fix55": 0, "header": 0}
    total_raw = 0

    for file in files:
        filename, rows = await parse_file(file)
        filenames.append(filename)
        result = process_rows(rows, filename, opts)
        all_contacts.extend(result.contacts)
        total_raw += result.total_raw
        for k in combined_fixes:
            combined_fixes[k] += result.fixes.get(k, 0)

    # Deduplicar dentro da sessão
    dup_count = 0
    if opts["dup"]:
        all_contacts, dup_count = deduplicate(all_contacts)
        combined_fixes["dup"] += dup_count

    # Contar por status
    valid = [c for c in all_contacts if c["status"] == "valid"]
    warn = [c for c in all_contacts if c["status"] == "warn"]
    err = [c for c in all_contacts if c["status"] == "err"]

    # Verificar duplicados globais (contatos que já existem no banco)
    global_dups = 0
    existing_phones = set()
    for c in valid + warn:
        phone_key = re.sub(r"\D", "", c["numero"])
        if phone_key:
            existing = db.query(Contact).filter(Contact.phone == phone_key).first()
            if existing:
                existing_phones.add(phone_key)
                global_dups += 1

    # Gerar ZIP apenas com válidos + warns
    processable = valid + warn
    chunks = split_chunks(processable, chunk_size)
    zip_bytes = generate_zip(chunks) if chunks else b""
    zip_path = save_zip(zip_bytes) if zip_bytes else None

    # Salvar sessão
    session = Session(
        filenames=filenames,
        total_raw=total_raw,
        total_valid=len(valid),
        total_warn=len(warn),
        total_err=len(err),
        duplicates_removed=dup_count,
        duplicates_global=global_dups,
        fixes=combined_fixes,
        chunk_size=chunk_size,
        zip_path=zip_path,
        status="done",
    )
    db.add(session)
    db.flush()

    # Salvar contatos no banco e criar relacionamentos
    for c in all_contacts:
        phone_key = re.sub(r"\D", "", c["numero"])
        if not phone_key:
            continue

        contact = db.query(Contact).filter(Contact.phone == phone_key).first()
        is_global_dup = phone_key in existing_phones

        if contact:
            contact.last_seen_at = __import__("datetime").datetime.utcnow()
            contact.session_count += 1
            if not contact.name and c["nome"]:
                contact.name = c["nome"]
        else:
            contact = Contact(phone=phone_key, name=c["nome"] or None)
            db.add(contact)
            db.flush()

        sc = SessionContact(
            session_id=session.id,
            contact_id=contact.id,
            was_duplicate_global=is_global_dup,
            status=c["status"],
            raw_name=c["nome"],
            raw_number=c["numero"],
        )
        db.add(sc)

    # Atualizar ML stats
    ml = db.query(MLStats).filter(MLStats.id == 1).first()
    if not ml:
        ml = MLStats(id=1)
        db.add(ml)

    ml.total_sessions = (ml.total_sessions or 0) + 1
    ml.total_processed = (ml.total_processed or 0) + total_raw
    ml.total_valid = (ml.total_valid or 0) + len(valid)
    ml.fixes_comma = (ml.fixes_comma or 0) + combined_fixes["comma"]
    ml.fixes_emoji = (ml.fixes_emoji or 0) + combined_fixes["emoji"]
    ml.fixes_dup = (ml.fixes_dup or 0) + combined_fixes["dup"]
    ml.fixes_fix55 = (ml.fixes_fix55 or 0) + combined_fixes["fix55"]
    ml.fixes_header = (ml.fixes_header or 0) + combined_fixes["header"]

    # Aprender padrões de prefixo
    patterns = ml.patterns or {}
    sample_nums = [re.sub(r"\D", "", c["numero"]) for c in valid if len(re.sub(r"\D", "", c["numero"])) >= 10]
    for d in sample_nums[:200]:
        prefix = d[:4]
        patterns[prefix] = patterns.get(prefix, 0) + 1
    ml.patterns = patterns

    # Log
    log = list(ml.log or [])
    from datetime import datetime
    msg = f"Processados {total_raw} contatos de {', '.join(filenames)} — {len(valid)} válidos"
    log.insert(0, {"date": datetime.utcnow().isoformat(), "msg": msg})
    ml.log = log[:50]

    db.commit()
    db.refresh(session)

    return UploadResponse(
        session_id=session.id,
        filenames=filenames,
        total_raw=total_raw,
        total_valid=len(valid),
        total_warn=len(warn),
        total_err=len(err),
        duplicates_removed=dup_count,
        duplicates_global=global_dups,
        fixes=combined_fixes,
        contacts=[ContactResult(**c) for c in all_contacts],
        chunks=len(chunks),
    )
