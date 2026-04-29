#!/usr/bin/env python3
"""
Orquestrador da coleta de vagas do LinkedIn.

Fluxo:
1. buscar URLs de vagas no LinkedIn
2. iterar sobre cada vaga encontrada
3. extrair os dados brutos da vaga
4. normalizar os dados extraidos
5. devolver uma lista final pronta para uso posterior no endpoint /analisar
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from scripts.coleta_dados.buscar_vagas_linkedin import (
    BuscaVagasLinkedInConfig,
    BuscadorVagasLinkedIn,
)
from scripts.coleta_dados.extrair_dados_vaga import (
    ExtracaoVagaConfig,
    ExtratorDadosVagaLinkedIn,
)
from scripts.coleta_dados.normalizar_vaga import normalizar_vaga


def coletar_vagas(
    cargo: Optional[str] = None,
    localizacao: Optional[str] = None,
    modalidade: Optional[str] = None,
    candidatura_simplificada: bool = True,
    max_links: int = 25,
    headless: bool = False,
    search_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executa o pipeline completo de coleta de vagas do LinkedIn.
    """
    buscador = BuscadorVagasLinkedIn(
        BuscaVagasLinkedInConfig(
            cargo=cargo,
            localizacao=localizacao,
            modalidade=modalidade,
            candidatura_simplificada=candidatura_simplificada,
            max_links=max_links,
            headless=headless,
            search_url=search_url,
        )
    )

    resultado_busca = buscador.buscar_urls()
    vagas_encontradas = resultado_busca.get("vagas", [])

    if resultado_busca.get("status") != "ok":
        return {
            "status": "erro",
            "total_encontradas": 0,
            "total_processadas": 0,
            "vagas": [],
            "mensagem": resultado_busca.get("mensagem", "Falha ao buscar vagas no LinkedIn."),
            "detalhes_busca": resultado_busca,
        }

    extrator = ExtratorDadosVagaLinkedIn(
        ExtracaoVagaConfig(headless=headless)
    )

    vagas_processadas: List[Dict[str, Any]] = []
    for vaga in vagas_encontradas:
        url_vaga = vaga.get("url_vaga", "")
        if not url_vaga:
            vagas_processadas.append(
                {
                    "status": "erro",
                    "url_vaga": "",
                    "titulo_vaga": "",
                    "empresa": "",
                    "localizacao": "",
                    "modalidade": "",
                    "tipo_vaga": "",
                    "texto_vaga": "",
                    "fonte_vaga": "LinkedIn",
                    "mensagem": "Registro retornado pela busca sem url_vaga.",
                }
            )
            continue

        dados_brutos = extrator.extrair(url_vaga)
        vaga_normalizada = normalizar_vaga(dados_brutos)
        vagas_processadas.append(vaga_normalizada)

    total_ok = sum(1 for vaga in vagas_processadas if vaga.get("status") == "ok")

    return {
        "status": "ok",
        "total_encontradas": len(vagas_encontradas),
        "total_processadas": len(vagas_processadas),
        "total_ok": total_ok,
        "vagas": vagas_processadas,
        "mensagem": "Pipeline de coleta concluido.",
    }


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa o pipeline de coleta de vagas do LinkedIn.")
    parser.add_argument("--cargo")
    parser.add_argument("--localizacao")
    parser.add_argument("--modalidade")
    parser.add_argument(
        "--todas-as-vagas",
        action="store_true",
        help="Desabilita o filtro de candidatura simplificada (Easy Apply)."
    )
    parser.add_argument("--max-links", type=int, default=25)
    parser.add_argument("--search-url")
    parser.add_argument("--headless", action="store_true")
    return parser


def main() -> int:
    args = criar_parser().parse_args()
    resultado = coletar_vagas(
        cargo=args.cargo,
        localizacao=args.localizacao,
        modalidade=args.modalidade,
        candidatura_simplificada=not args.todas_as_vagas,
        max_links=args.max_links,
        headless=args.headless,
        search_url=args.search_url,
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
