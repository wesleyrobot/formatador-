"""
Proxy para a API Google Gemini — a chave fica no servidor, não exposta no browser.
Modelo gratuito: gemini-2.0-flash
"""
import os
import json
import httpx
from fastapi import APIRouter, HTTPException
from ..schemas import AIAnalyzeIn, AIDeepIn

router = APIRouter()

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY não configurada no servidor")
    return key


async def _gemini_call(api_key: str, prompt: str) -> str:
    """Chama a API Gemini e retorna o texto da resposta."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.2},
    }
    url = f"{GEMINI_URL}?key={api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Erro Gemini: {resp.text}")

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise HTTPException(status_code=500, detail="Resposta inesperada do Gemini")


@router.post("/ai/analyze")
async def ai_analyze(body: AIAnalyzeIn):
    """Analisa estrutura do arquivo e detecta colunas/problemas via IA."""
    api_key = _get_api_key()

    sample_text = "\n".join(
        [f"Linha {i+1}: {row}" for i, row in enumerate(body.sample_rows[:15])]
    )
    prompt = f"""Você é um especialista em análise de planilhas de contatos. Analise as linhas abaixo e retorne um JSON com:
- hasHeader (boolean): se a primeira linha é cabeçalho
- nameCol (0 ou 1): índice da coluna de nomes
- numCol (0 ou 1): índice da coluna de números
- separator (",", ";", "tab"): delimitador detectado
- totalRows (número estimado): {body.total_rows}
- issues (array de strings): problemas encontrados
- fixSuggestions (array de strings): correções sugeridas
- quality ("boa", "média", "ruim"): qualidade geral dos dados
- summary (string): resumo em 1-2 frases

Arquivo: {body.filename}
Total de linhas: {body.total_rows}

Amostra:
{sample_text}

Responda APENAS com o JSON, sem markdown, sem texto extra."""

    content = await _gemini_call(api_key, prompt)

    # Limpar markdown se presente
    clean = content.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"summary": content, "quality": "média", "issues": []}


@router.post("/ai/deep")
async def ai_deep_analysis(body: AIDeepIn):
    """Análise profunda dos padrões aprendidos."""
    api_key = _get_api_key()

    stats = body.stats
    top_patterns = sorted(stats.patterns.items(), key=lambda x: x[1], reverse=True)[:10]
    patterns_text = ", ".join(f"{p}... ({c} ocorrências)" for p, c in top_patterns)
    accuracy = round((stats.total_valid / stats.total_processed * 100) if stats.total_processed else 0)

    prompt = f"""Você é um especialista em qualidade de dados de contato. Analise estes dados e gere insights.

DADOS:
- Sessões: {stats.total_sessions}
- Total processados: {stats.total_processed}
- Total válidos: {stats.total_valid}
- Precisão: {accuracy}%
- Fixes: vírgulas={stats.fixes_comma}, emojis={stats.fixes_emoji}, duplicados={stats.fixes_dup}, +55={stats.fixes_fix55}, cabeçalhos={stats.fixes_header}
- DDDs mais comuns: {patterns_text or "nenhum ainda"}

Gere uma análise com:
1. Insights sobre qualidade dos dados
2. Padrões nos DDDs
3. Recomendações para os próximos processamentos

Seja direto e técnico, máximo 200 palavras, em português."""

    content = await _gemini_call(api_key, prompt)
    return {"analysis": content}
