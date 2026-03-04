"""
Lógica de processamento de contatos migrada do JavaScript.
Equivalente às funções: rmEmoji, fix55, valNum, detectColumns, detectHeader,
processRows, deduplicate, splitChunks, generateZip.
"""
import re
import io
import csv
import zipfile
from datetime import datetime
from typing import List, Dict, Tuple, Optional


# ─── Normalização ────────────────────────────────────────────────────────────

def rm_emoji(s: str) -> str:
    """Remove emojis de nomes."""
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001FAFF"
        "\U00002600-\U000027BF"
        "\U00002764\uFE0F]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", s).strip()


def fix_55(num: str) -> str:
    """Adiciona código 55 (Brasil) a números de 10-11 dígitos sem prefixo."""
    d = re.sub(r"\D", "", str(num))
    if not d:
        return num
    if len(d) in (10, 11) and not d.startswith("55"):
        return "55" + d
    return d


def val_num(num: str) -> List[str]:
    """Valida número de telefone. Retorna lista de problemas encontrados."""
    s = str(num)
    d = re.sub(r"\D", "", s)
    issues = []

    if not d:
        issues.append("vazio")
        return issues
    if re.search(r"[a-zA-Z]", s):
        issues.append("contém letras")
    if len(d) < 10 or len(d) > 13:
        issues.append(f"{len(d)} dígitos")
    elif not d.startswith("55"):
        issues.append("sem código 55")
    return issues


# ─── Detecção de colunas ─────────────────────────────────────────────────────

_HEADER_KEYWORDS = {
    "nome", "name", "contato", "contact", "número", "numero", "number",
    "telefone", "phone", "cel", "celular", "whatsapp", "fone", "tel",
    "cliente", "client", "lista", "list",
}

_NUMBER_PATTERN = re.compile(r"^\+?[\d\s\-\(\)]{7,}$")


def _looks_like_number(val: str) -> bool:
    return bool(_NUMBER_PATTERN.match(val.strip()))


def _looks_like_name(val: str) -> bool:
    d = re.sub(r"\D", "", val)
    return len(d) < len(val) * 0.5  # menos da metade são dígitos


def detect_header(row: List[str]) -> bool:
    """Retorna True se a linha parece ser um cabeçalho."""
    if not row:
        return False
    for cell in row:
        if str(cell).strip().lower() in _HEADER_KEYWORDS:
            return True
    return False


def detect_columns(rows: List[List[str]]) -> Tuple[Optional[int], Optional[int]]:
    """
    Detecta qual coluna contém nomes e qual contém números.
    Retorna (name_col, num_col). None se não detectado.
    """
    if not rows:
        return None, None

    # Amostrar até 20 linhas (ignorar possível cabeçalho)
    sample = rows[1:21] if detect_header(rows[0]) else rows[:20]
    if not sample:
        return None, None

    num_cols = len(sample[0])
    if num_cols == 1:
        return None, 0
    if num_cols >= 2:
        # Contar scores: quantas células de cada coluna parecem números
        num_scores = [0] * num_cols
        for row in sample:
            for i, cell in enumerate(row):
                if i >= num_cols:
                    continue
                if _looks_like_number(str(cell)):
                    num_scores[i] += 1

        best_num_col = max(range(num_cols), key=lambda i: num_scores[i])
        name_col = 0 if best_num_col != 0 else 1

        if num_scores[best_num_col] > len(sample) * 0.3:
            return name_col, best_num_col

    return None, None


# ─── Pipeline principal ───────────────────────────────────────────────────────

class ProcessResult:
    def __init__(self):
        self.contacts: List[Dict] = []
        self.fixes = {"comma": 0, "emoji": 0, "dup": 0, "fix55": 0, "header": 0}
        self.total_raw = 0
        self.had_header = False


def process_rows(
    rows: List[List[str]],
    filename: str,
    opts: Dict,
    name_col: Optional[int] = None,
    num_col: Optional[int] = None,
) -> ProcessResult:
    """
    Processa linhas brutas de um arquivo e retorna contatos normalizados.
    opts: {emoji, dup, val, fix55, fixc}
    """
    result = ProcessResult()

    if not rows:
        return result

    # Detectar cabeçalho
    if detect_header(rows[0]):
        rows = rows[1:]
        result.had_header = True
        result.fixes["header"] += 1

    result.total_raw = len(rows)

    # Detectar colunas se não informado
    if name_col is None and num_col is None:
        name_col, num_col = detect_columns(rows)

    for row in rows:
        if not any(str(c).strip() for c in row):
            continue

        nome = ""
        numero = ""

        num_cols = len(row)

        if num_cols == 1:
            # Só número
            val = str(row[0]).strip()
            # Verificar se há vírgula separando nome,número
            if opts.get("fixc") and "," in val:
                parts = val.split(",", 1)
                nome = parts[0].strip()
                numero = parts[1].strip()
                result.fixes["comma"] += 1
            else:
                numero = val

        elif num_cols == 2:
            if num_col is not None:
                numero = str(row[num_col]).strip()
                other = 1 - num_col
                nome = str(row[other]).strip() if other < num_cols else ""
            else:
                # Heurística: qual parece número?
                if _looks_like_number(str(row[1])):
                    nome, numero = str(row[0]).strip(), str(row[1]).strip()
                elif _looks_like_number(str(row[0])):
                    numero, nome = str(row[0]).strip(), str(row[1]).strip()
                else:
                    nome, numero = str(row[0]).strip(), str(row[1]).strip()

        else:
            # 3+ colunas
            if opts.get("fixc"):
                # Unir colunas extras com vírgula
                if num_col is not None and name_col is not None:
                    numero = str(row[num_col]).strip()
                    name_parts = [str(row[i]).strip() for i in range(num_cols) if i != num_col]
                    nome = ", ".join(p for p in name_parts if p)
                else:
                    # Tentar detectar: última coluna que parece número
                    num_idx = None
                    for i in range(num_cols - 1, -1, -1):
                        if _looks_like_number(str(row[i])):
                            num_idx = i
                            break
                    if num_idx is not None:
                        numero = str(row[num_idx]).strip()
                        name_parts = [str(row[i]).strip() for i in range(num_cols) if i != num_idx]
                        nome = ", ".join(p for p in name_parts if p)
                    else:
                        nome = ", ".join(str(c).strip() for c in row[:-1])
                        numero = str(row[-1]).strip()
                result.fixes["comma"] += 1
            else:
                nome = str(row[0]).strip()
                numero = str(row[1]).strip() if num_cols > 1 else ""

        # Aplicar transformações
        if opts.get("emoji") and nome:
            cleaned = rm_emoji(nome)
            if cleaned != nome:
                result.fixes["emoji"] += 1
            nome = cleaned

        if opts.get("fix55") and numero:
            fixed = fix_55(numero)
            if fixed != numero:
                result.fixes["fix55"] += 1
            numero = fixed

        # Validar
        issues = val_num(numero) if opts.get("val") else []
        if issues:
            status = "err" if "vazio" in issues or "contém letras" in issues else "warn"
        else:
            status = "valid"

        result.contacts.append({
            "nome": nome,
            "numero": numero,
            "status": status,
            "issues": issues,
            "file": filename,
        })

    return result


# ─── Deduplicação ────────────────────────────────────────────────────────────

def deduplicate(contacts: List[Dict]) -> Tuple[List[Dict], int]:
    """Remove duplicados dentro da mesma sessão. Retorna (lista_dedup, count_removidos)."""
    seen: set = set()
    dedup = []
    removed = 0
    for c in contacts:
        key = re.sub(r"\D", "", c["numero"])
        if key not in seen:
            seen.add(key)
            dedup.append(c)
        else:
            removed += 1
    return dedup, removed


# ─── Geração de ZIP ───────────────────────────────────────────────────────────

def split_chunks(contacts: List[Dict], size: int) -> List[List[Dict]]:
    """Divide lista de contatos em chunks de tamanho `size`."""
    return [contacts[i : i + size] for i in range(0, len(contacts), size)]


def generate_zip(chunks: List[List[Dict]], date_str: Optional[str] = None) -> bytes:
    """
    Gera um ZIP em memória com um CSV por chunk.
    Retorna os bytes do ZIP.
    """
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, chunk in enumerate(chunks, 1):
            csv_buf = io.StringIO()
            writer = csv.writer(csv_buf, quoting=csv.QUOTE_MINIMAL)
            for c in chunk:
                nome = c["nome"]
                # Envolver em aspas se contiver vírgula
                if "," in nome:
                    nome = f'"{nome}"'
                writer.writerow([nome, c["numero"]])
            filename = f"Lista_{i:03d}.csv"
            zf.writestr(filename, csv_buf.getvalue())

    return buf.getvalue()
