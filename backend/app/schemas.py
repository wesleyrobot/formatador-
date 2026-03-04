from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# --- Upload ---

class ProcessOptions(BaseModel):
    emoji: bool = True
    dup: bool = True
    val: bool = True
    fix55: bool = True
    fixc: bool = True
    chunk_size: int = 49


class ContactResult(BaseModel):
    nome: str
    numero: str
    status: str          # 'valid', 'warn', 'err'
    issues: List[str]
    file: str


class UploadResponse(BaseModel):
    session_id: int
    filenames: List[str]
    total_raw: int
    total_valid: int
    total_warn: int
    total_err: int
    duplicates_removed: int
    duplicates_global: int
    fixes: Dict[str, int]
    contacts: List[ContactResult]
    chunks: int


# --- Sessions ---

class SessionSummary(BaseModel):
    id: int
    created_at: datetime
    filenames: List[str]
    total_raw: int
    total_valid: int
    total_warn: int
    total_err: int
    duplicates_removed: int
    duplicates_global: int
    chunks: int
    status: str

    class Config:
        from_attributes = True


class SessionDetail(SessionSummary):
    fixes: Dict[str, Any]
    contacts: List[ContactResult]


# --- Contacts ---

class ContactOut(BaseModel):
    id: int
    phone: str
    name: Optional[str]
    first_seen_at: datetime
    last_seen_at: datetime
    session_count: int

    class Config:
        from_attributes = True


class ContactsPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ContactOut]


# --- ML ---

class MLStatsOut(BaseModel):
    total_sessions: int
    total_processed: int
    total_valid: int
    fixes_comma: int
    fixes_emoji: int
    fixes_dup: int
    fixes_fix55: int
    fixes_header: int
    patterns: Dict[str, int]
    log: List[Dict[str, str]]


class MLLearnIn(BaseModel):
    total: int = 0
    valid: int = 0
    fixed_comma: int = 0
    fixed_emoji: int = 0
    dups: int = 0
    fix55: int = 0
    had_header: bool = False
    sample_numbers: List[str] = []
    msg: str = ""


# --- AI Proxy ---

class AIAnalyzeIn(BaseModel):
    sample_rows: List[List[str]]
    filename: str
    total_rows: int


class AIDeepIn(BaseModel):
    stats: MLStatsOut
    history: List[Dict[str, Any]]
