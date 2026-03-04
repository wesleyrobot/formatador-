from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    filenames = Column(JSON, default=list)
    total_raw = Column(Integer, default=0)
    total_valid = Column(Integer, default=0)
    total_warn = Column(Integer, default=0)
    total_err = Column(Integer, default=0)
    duplicates_removed = Column(Integer, default=0)
    duplicates_global = Column(Integer, default=0)  # dups de sessões anteriores
    fixes = Column(JSON, default=dict)              # {comma, emoji, fix55, header}
    chunk_size = Column(Integer, default=49)
    zip_path = Column(Text, nullable=True)          # path do ZIP salvo no servidor
    status = Column(String(20), default="done")

    contacts = relationship("SessionContact", back_populates="session", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    session_count = Column(Integer, default=1)

    sessions = relationship("SessionContact", back_populates="contact")


class SessionContact(Base):
    __tablename__ = "session_contacts"

    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), primary_key=True)
    was_duplicate_global = Column(Boolean, default=False)
    status = Column(String(10))   # 'valid', 'warn', 'err'
    raw_name = Column(Text, nullable=True)
    raw_number = Column(Text, nullable=True)

    session = relationship("Session", back_populates="contacts")
    contact = relationship("Contact", back_populates="sessions")


class MLStats(Base):
    __tablename__ = "ml_stats"

    id = Column(Integer, primary_key=True, default=1)
    total_sessions = Column(Integer, default=0)
    total_processed = Column(Integer, default=0)
    total_valid = Column(Integer, default=0)
    fixes_comma = Column(Integer, default=0)
    fixes_emoji = Column(Integer, default=0)
    fixes_dup = Column(Integer, default=0)
    fixes_fix55 = Column(Integer, default=0)
    fixes_header = Column(Integer, default=0)
    patterns = Column(JSON, default=dict)   # {"5585": 125}
    log = Column(JSON, default=list)        # últimas 50 entradas
