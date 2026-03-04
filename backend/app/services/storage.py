"""
Gerenciamento de ZIPs gerados no servidor.
"""
import os
import uuid
from pathlib import Path

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "/tmp/contactprocessor_zips"))


def ensure_storage():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_zip(zip_bytes: bytes) -> str:
    """Salva ZIP e retorna o path relativo."""
    ensure_storage()
    filename = f"{uuid.uuid4().hex}.zip"
    path = STORAGE_DIR / filename
    path.write_bytes(zip_bytes)
    return str(path)


def load_zip(path: str) -> bytes:
    """Lê ZIP do disco."""
    return Path(path).read_bytes()


def delete_zip(path: str):
    """Remove ZIP do disco se existir."""
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass
