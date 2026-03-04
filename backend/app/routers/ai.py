"""
Proxy para a API Anthropic — a chave fica no servidor, não exposta no browser.
"""
import os
import httpx
from fastapi import APIRouter, HTTPException
from ..schemas import AIAnalyzeIn, AIDeepIn

router = APIRouter()

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"


def _get_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY não configurada no servidor")
    return key


def _anthropic_headers(api_key: str) -> dict:
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


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

Responda APENAS com o JSON, sem markdown."""

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(ANTHROPIC_URL, headers=_anthropic_headers(api_key), json=payload)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Erro Anthropic: {resp.text}")

    data = resp.json()
    content = data["content"][0]["text"] if data.get("content") else ""

    # Limpar markdown se presente
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    import json
    try:
        result = json.loads(content.strip())
    except json.JSONDecodeError:
        result = {"summary": content, "quality": "média", "issues": []}

    return result


@router.post("/ai/deep")
async def ai_deep_analysis(body: AIDeepIn):
    """Análise profunda dos padrões aprendidos (substitui runDeepAnalysis do frontend)."""
    api_key = _get_api_key()

    stats = body.stats
    top_patterns = sorted(stats.patterns.items(), key=lambda x: x[1], reverse=True)[:10]
    patterns_text = ", ".join(f"{p}... ({c} ocorrências)" for p, c in top_patterns)
    accuracy = round((stats.total_valid / stats.total_processed * 100) if stats.total_processed else 0)

    prompt = f"""Você é um motor de deep learning especializado em dados de contato. Analise estes dados de aprendizado acumulado e gere insights.

DADOS DE APRENDIZADO:
- Sessões de processamento: {stats.total_sessions}
- Total de contatos processados: {stats.total_processed}
- Total de contatos válidos: {stats.total_valid}
- Precisão atual: {accuracy}%
- Fixes aplicados: vírgulas={stats.fixes_comma}, emojis={stats.fixes_emoji}, duplicados={stats.fixes_dup}, +55={stats.fixes_fix55}, cabeçalhos={stats.fixes_header}
- Prefixos de DDD mais comuns: {patterns_text or "nenhum ainda"}

Gere uma análise com:
1. Insights sobre a qualidade dos dados
2. Padrões identificados nos números (DDDs predominantes)
3. Recomendações de configuração para os próximos processamentos

Seja direto e técnico, use no máximo 200 palavras."""

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(ANTHROPIC_URL, headers=_anthropic_headers(api_key), json=payload)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Erro Anthropic: {resp.text}")

    data = resp.json()
    content = data["content"][0]["text"] if data.get("content") else ""
    return {"analysis": content}
