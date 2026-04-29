import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from scripts.analise.analisar_vaga import AnalisadorVagas

app = FastAPI(title="Agente IA - Analise de Vagas")
BROWSER_AUTOMATION_ENABLED = os.getenv("BROWSER_AUTOMATION_ENABLED", "true").lower() == "true"


class VagaRequest(BaseModel):
    vaga: str
    url_vaga: str | None = None
    fonte_vaga: str | None = None


class CandidaturaRequest(BaseModel):
    limite: int = 20
    incluir_revisao_manual: bool = False
    dry_run: bool = False


@app.get("/")
def home():
    return {"status": "ok", "mensagem": "API rodando"}


@app.post("/analisar")
def analisar_vaga(request: VagaRequest):
    analisador = AnalisadorVagas()
    resultado = analisador.analisar_vaga(
        vaga_texto=request.vaga,
        url_vaga=request.url_vaga,
        fonte_vaga=request.fonte_vaga,
    )

    if not resultado:
        raise HTTPException(status_code=500, detail="Erro ao analisar vaga")

    return resultado


@app.post("/candidatar")
def executar_candidaturas(request: CandidaturaRequest):
    if not BROWSER_AUTOMATION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Automacao com navegador desabilitada neste ambiente. Rode a candidatura localmente com Playwright.",
        )

    try:
        from scripts.candidatura.executar_candidaturas import executar_fila_candidaturas

        resultado = executar_fila_candidaturas(
            limite=request.limite,
            incluir_revisao_manual=request.incluir_revisao_manual,
            dry_run=request.dry_run,
        )
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar candidaturas: {e}")


@app.post("/coletar")
def coletar_endpoint():
    if not BROWSER_AUTOMATION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Coleta com navegador desabilitada neste ambiente. Rode a coleta localmente com Playwright.",
        )

    from scripts.coleta_dados.coletar_vagas_pipeline import coletar_vagas

    resultado = coletar_vagas(
        cargo="estagio ti",
        localizacao="Sao Paulo, SP",
        candidatura_simplificada=True,
        max_links=2,
    )
    return resultado
