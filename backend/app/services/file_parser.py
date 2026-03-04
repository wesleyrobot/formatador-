"""
Parsing de arquivos: CSV, TXT, XLSX, XLS, ZIP, RAR.
"""
import io
import csv
import zipfile
from typing import List, Tuple
from fastapi import UploadFile, HTTPException


async def parse_file(file: UploadFile) -> Tuple[str, List[List[str]]]:
    """
    Recebe um UploadFile e retorna (filename, rows).
    rows é uma lista de listas de strings.
    """
    content = await file.read()
    name = file.filename or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

    if ext in ("csv", "txt"):
        return name, _parse_csv_bytes(content)
    elif ext in ("xlsx", "xls"):
        return name, _parse_excel_bytes(content, ext)
    elif ext == "zip":
        return name, _parse_zip_bytes(content)
    elif ext == "rar":
        return name, _parse_rar_bytes(content)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: .{ext}. Use CSV, TXT, XLSX, XLS, ZIP ou RAR.",
        )


def _parse_csv_bytes(content: bytes) -> List[List[str]]:
    """Parse CSV/TXT — tenta detectar encoding e delimitador automaticamente."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("latin-1", errors="replace")

    # Detectar delimitador
    sample = text[:2048]
    delimiter = ";"
    if text.count(",") > text.count(";"):
        delimiter = ","
    if text.count("\t") > max(text.count(","), text.count(";")):
        delimiter = "\t"

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(c.strip() for c in row)]
    return rows


def _parse_excel_bytes(content: bytes, ext: str) -> List[List[str]]:
    """Parse XLSX/XLS usando openpyxl ou xlrd."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            str_row = [str(c) if c is not None else "" for c in row]
            if any(c.strip() for c in str_row):
                rows.append(str_row)
        wb.close()
        return rows
    except Exception:
        pass

    # Fallback: pandas
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(content), header=None, dtype=str)
        df = df.fillna("")
        return df.values.tolist()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler Excel: {e}")


def _parse_zip_bytes(content: bytes) -> List[List[str]]:
    """Extrai e processa todos os arquivos CSV/XLSX dentro do ZIP."""
    all_rows: List[List[str]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.startswith("__MACOSX") or name.endswith("/"):
                    continue
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                file_bytes = zf.read(name)
                if ext in ("csv", "txt"):
                    all_rows.extend(_parse_csv_bytes(file_bytes))
                elif ext in ("xlsx", "xls"):
                    all_rows.extend(_parse_excel_bytes(file_bytes, ext))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Arquivo ZIP inválido ou corrompido.")
    return all_rows


def _parse_rar_bytes(content: bytes) -> List[List[str]]:
    """Extrai e processa arquivos CSV/XLSX dentro de um RAR."""
    import tempfile
    import os

    try:
        import rarfile
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="Suporte a RAR não instalado. Use ZIP ou instale rarfile+unrar.",
        )

    all_rows: List[List[str]] = []
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with rarfile.RarFile(tmp_path) as rf:
            for info in rf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                file_bytes = rf.read(info)
                if ext in ("csv", "txt"):
                    all_rows.extend(_parse_csv_bytes(file_bytes))
                elif ext in ("xlsx", "xls"):
                    all_rows.extend(_parse_excel_bytes(file_bytes, ext))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler RAR: {e}")
    finally:
        os.unlink(tmp_path)

    return all_rows
