#!/usr/bin/env python3
"""
Executa a fila de candidaturas a partir das vagas analisadas no Supabase.

Fluxo:
- busca vagas elegiveis
- escolhe o executor por fonte
- registra a candidatura no banco
- executa a automacao quando houver suporte
- atualiza candidaturas e vagas_analisadas com o resultado final
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from scripts.candidatura.linkedin_easy_apply_executor import LinkedInEasyApplyExecutor
from scripts.compartilhado.supabase_client import SupabaseClient


@dataclass
class PlanoCandidatura:
    status_candidatura: str
    status_fluxo: str
    payload_candidatura: Dict[str, Any]
    observacoes: str
    mensagem_enviada: Optional[str] = None
    curriculo_usado: Optional[str] = None
    executar_automaticamente: bool = False


class BaseExecutor:
    fonte = "Generica"

    def preparar(self, vaga: Dict[str, Any]) -> PlanoCandidatura:
        raise NotImplementedError

    def executar(self, vaga: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class LinkedInExecutor(BaseExecutor):
    fonte = "LinkedIn"

    def __init__(self, headless: bool = False) -> None:
        self.easy_apply_executor = LinkedInEasyApplyExecutor(headless=headless)

    def preparar(self, vaga: Dict[str, Any]) -> PlanoCandidatura:
        payload = {
            "fonte": self.fonte,
            "empresa": vaga.get("empresa"),
            "titulo_vaga": vaga.get("titulo_vaga"),
            "url_vaga": vaga.get("url_vaga"),
            "estrategia": "linkedin_easy_apply",
            "match_score": vaga.get("match_score"),
        }
        return PlanoCandidatura(
            status_candidatura="pendente",
            status_fluxo="aprovada_para_candidatura",
            payload_candidatura=payload,
            observacoes="Vaga preparada para execucao via LinkedIn Easy Apply.",
            executar_automaticamente=True,
        )

    def executar(self, vaga: Dict[str, Any]) -> Dict[str, Any]:
        return self.easy_apply_executor.executar(vaga)


class IndeedExecutor(BaseExecutor):
    fonte = "Indeed"

    def preparar(self, vaga: Dict[str, Any]) -> PlanoCandidatura:
        payload = {
            "fonte": self.fonte,
            "empresa": vaga.get("empresa"),
            "titulo_vaga": vaga.get("titulo_vaga"),
            "url_vaga": vaga.get("url_vaga"),
            "estrategia": "revisar_fluxo_indeed",
            "match_score": vaga.get("match_score"),
        }
        return PlanoCandidatura(
            status_candidatura="em_revisao",
            status_fluxo="revisao_manual",
            payload_candidatura=payload,
            observacoes=(
                "Vaga do Indeed enviada para revisao manual. "
                "Ainda nao existe executor automatico implementado."
            ),
        )

    def executar(self, vaga: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "revisao_manual",
            "observacoes": "Executor do Indeed ainda nao implementado."
        }


class GenericExecutor(BaseExecutor):
    fonte = "Generica"

    def preparar(self, vaga: Dict[str, Any]) -> PlanoCandidatura:
        payload = {
            "fonte": vaga.get("fonte_vaga") or self.fonte,
            "empresa": vaga.get("empresa"),
            "titulo_vaga": vaga.get("titulo_vaga"),
            "url_vaga": vaga.get("url_vaga"),
            "estrategia": "revisar_formulario_externo",
            "match_score": vaga.get("match_score"),
        }
        return PlanoCandidatura(
            status_candidatura="em_revisao",
            status_fluxo="revisao_manual",
            payload_candidatura=payload,
            observacoes=(
                "Fonte sem executor automatico. Candidatura registrada para revisao manual."
            ),
        )

    def executar(self, vaga: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "revisao_manual",
            "observacoes": "Nao existe executor automatico para esta fonte."
        }


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Executa candidaturas a partir de vagas analisadas no Supabase."
    )
    parser.add_argument("--limite", type=int, default=20)
    parser.add_argument("--incluir-revisao-manual", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--headless", action="store_true")
    return parser


def criar_cliente() -> SupabaseClient:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL e SUPABASE_KEY precisam estar configuradas.")
    return SupabaseClient(supabase_url, supabase_key)


def obter_executor(fonte_vaga: Optional[str], headless: bool = False) -> BaseExecutor:
    fonte_normalizada = (fonte_vaga or "").strip().lower()
    if "linkedin" in fonte_normalizada:
        return LinkedInExecutor(headless=headless)
    if "indeed" in fonte_normalizada:
        return IndeedExecutor()
    return GenericExecutor()


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapear_resultado_execucao(resultado_execucao: Dict[str, Any]) -> Dict[str, str]:
    status = resultado_execucao.get("status", "erro")

    if status == "candidatura_enviada":
        return {
            "status_candidatura": "enviada",
            "status_fluxo": "candidatura_executada",
        }

    if status in {
        "easy_apply_pronto_para_revisao",
        "easy_apply_requer_revisao_manual",
        "login_necessario",
        "nao_e_easy_apply",
        "revisao_manual",
    }:
        return {
            "status_candidatura": "em_revisao",
            "status_fluxo": "revisao_manual",
        }

    return {
        "status_candidatura": "falhou",
        "status_fluxo": "erro",
    }


def processar_vaga(
    client: SupabaseClient,
    vaga: Dict[str, Any],
    dry_run: bool = False,
    headless: bool = False,
) -> Dict[str, Any]:
    candidatura_existente = client.buscar_candidatura_por_vaga(vaga["id"])
    if candidatura_existente:
        return {
            "vaga_id": vaga["id"],
            "empresa": vaga.get("empresa"),
            "resultado": "ignorada",
            "motivo": f"candidatura_ja_existente:{candidatura_existente['status_candidatura']}",
        }

    executor = obter_executor(vaga.get("fonte_vaga"), headless=headless)
    plano = executor.preparar(vaga)

    if dry_run:
        return {
            "vaga_id": vaga["id"],
            "empresa": vaga.get("empresa"),
            "resultado": "dry_run",
            "fonte": vaga.get("fonte_vaga"),
            "status_candidatura": plano.status_candidatura,
            "status_fluxo": plano.status_fluxo,
            "executar_automaticamente": plano.executar_automaticamente,
        }

    resultado_execucao: Dict[str, Any]
    if plano.executar_automaticamente:
        resultado_execucao = executor.executar(vaga)
    else:
        resultado_execucao = {
            "status": "revisao_manual",
            "observacoes": plano.observacoes,
        }

    status_mapeado = _mapear_resultado_execucao(resultado_execucao)
    payload_final = {
        **plano.payload_candidatura,
        "resultado_execucao": resultado_execucao,
    }

    candidatura = client.criar_candidatura(
        vaga_id=vaga["id"],
        status_candidatura=status_mapeado["status_candidatura"],
        mensagem_enviada=plano.mensagem_enviada,
        curriculo_usado=plano.curriculo_usado,
        payload_candidatura=payload_final,
        retorno_site=resultado_execucao.get("status"),
        observacoes=resultado_execucao.get("observacoes", plano.observacoes),
        data_envio=_agora_iso() if status_mapeado["status_candidatura"] == "enviada" else None,
    )

    if not candidatura:
        return {
            "vaga_id": vaga["id"],
            "empresa": vaga.get("empresa"),
            "resultado": "erro",
            "motivo": "falha_ao_criar_candidatura",
        }

    client.atualizar_status_vaga(vaga["id"], status_mapeado["status_fluxo"])

    return {
        "vaga_id": vaga["id"],
        "empresa": vaga.get("empresa"),
        "resultado": "executada" if plano.executar_automaticamente else "registrada",
        "candidatura_id": candidatura.get("id"),
        "status_candidatura": status_mapeado["status_candidatura"],
        "status_fluxo": status_mapeado["status_fluxo"],
        "resultado_execucao": resultado_execucao.get("status"),
    }


def imprimir_resumo(resultados: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 60)
    print("FILA DE CANDIDATURAS")
    print("=" * 60)

    if not resultados:
        print("[!] Nenhuma vaga elegivel encontrada.")
        return

    for resultado in resultados:
        empresa = resultado.get("empresa", "Empresa nao informada")
        print(f"- {empresa}: {resultado['resultado']}")
        if "status_candidatura" in resultado:
            print(f"  status_candidatura={resultado['status_candidatura']}")
        if "status_fluxo" in resultado:
            print(f"  status_fluxo={resultado['status_fluxo']}")
        if "resultado_execucao" in resultado:
            print(f"  resultado_execucao={resultado['resultado_execucao']}")
        if "motivo" in resultado:
            print(f"  motivo={resultado['motivo']}")


def executar_fila_candidaturas(
    limite: int = 20,
    incluir_revisao_manual: bool = False,
    dry_run: bool = False,
    headless: bool = False,
) -> Dict[str, Any]:
    client = criar_cliente()
    vagas = client.listar_vagas_para_candidatura(
        limite=limite,
        incluir_revisao_manual=incluir_revisao_manual,
    )

    if vagas is None:
        return {
            "status": "erro",
            "mensagem": "Nao foi possivel listar vagas elegiveis.",
            "resultados": [],
        }

    resultados = [
        processar_vaga(client, vaga, dry_run=dry_run, headless=headless)
        for vaga in vagas
    ]

    return {
        "status": "ok",
        "total_vagas_recebidas": len(vagas),
        "total_processadas": len(resultados),
        "resultados": resultados,
    }
def main() -> int:
    parser = criar_parser()
    args = parser.parse_args()

    try:
        resposta = executar_fila_candidaturas(
            limite=args.limite,
            incluir_revisao_manual=args.incluir_revisao_manual,
            dry_run=args.dry_run,
            headless=args.headless,
        )
    except Exception as e:
        print(f"[x] Erro ao executar fila: {e}")
        return 1

    imprimir_resumo(resposta["resultados"])
    return 0 if resposta["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
