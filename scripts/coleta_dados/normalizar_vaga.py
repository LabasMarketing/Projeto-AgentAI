#!/usr/bin/env python3
"""
Normaliza os dados brutos extraidos de uma vaga do LinkedIn.

Responsabilidades:
- limpar e padronizar campos
- produzir um JSON final consistente
- respeitar o status retornado pelo extrator
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict, List


def _limpar_texto(valor: Any) -> str:
    texto = "" if valor is None else str(valor)
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_modalidade(valor: str, texto_vaga: str = "") -> str:
    combinado = f"{valor} {texto_vaga}".lower()
    if "híbrido" in combinado or "hibrido" in combinado or "hybrid" in combinado:
        return "Híbrido"
    if "remoto" in combinado or "remote" in combinado:
        return "Remoto"
    if "presencial" in combinado or "on-site" in combinado or "onsite" in combinado:
        return "Presencial"
    return ""


def _normalizar_tipo_vaga(valor: str, texto_vaga: str = "") -> str:
    combinado = f"{valor} {texto_vaga}".lower()
    regras = [
        ("estágio", "Estágio"),
        ("estagio", "Estágio"),
        ("internship", "Estágio"),
        ("clt", "CLT"),
        ("pj", "PJ"),
        ("temporário", "Temporário"),
        ("temporario", "Temporário"),
        ("full-time", "Tempo integral"),
        ("part-time", "Meio período"),
        ("meio período", "Meio período"),
        ("tempo integral", "Tempo integral"),
    ]
    for termo, valor_normalizado in regras:
        if termo in combinado:
            return valor_normalizado
    return _limpar_texto(valor)


def _normalizar_localizacao(valor: str) -> str:
    valor = _limpar_texto(valor)
    if not valor:
        return ""

    separadores = ["·", "•", "|"]
    partes = [valor]
    for separador in separadores:
        novas_partes: List[str] = []
        for parte in partes:
            novas_partes.extend([item.strip() for item in parte.split(separador) if item.strip()])
        partes = novas_partes

    candidatos = [parte for parte in partes if not any(char.isdigit() for char in parte)]
    return candidatos[0] if candidatos else partes[0]


def _compactar_texto_vaga(valor: str) -> str:
    texto = _limpar_texto(valor)
    prefixos_ruido = [
        "descrição da vaga",
        "descricao da vaga",
        "about the job",
        "job description",
    ]
    texto_lower = texto.lower()
    for prefixo in prefixos_ruido:
        if texto_lower.startswith(prefixo):
            texto = texto[len(prefixo):].strip(" :-")
            break
    return _limpar_texto(texto)


def normalizar_vaga(dados_brutos: Dict[str, Any]) -> Dict[str, Any]:
    status_entrada = _limpar_texto(dados_brutos.get("status", "ok")) or "ok"

    if status_entrada != "ok":
        return {
            "status": "erro",
            "url_vaga": _limpar_texto(dados_brutos.get("url_vaga", "")),
            "titulo_vaga": "",
            "empresa": "",
            "localizacao": "",
            "modalidade": "",
            "tipo_vaga": "",
            "texto_vaga": "",
            "fonte_vaga": "LinkedIn",
            "mensagem": _limpar_texto(dados_brutos.get("mensagem", "Falha na etapa de extracao.")),
            "dados_brutos_debug": {
                "texto_topo_vaga": _limpar_texto(dados_brutos.get("texto_topo_vaga", "")),
                "texto_total_pagina": _limpar_texto(dados_brutos.get("texto_total_pagina", "")),
            },
        }

    texto_vaga = _compactar_texto_vaga(dados_brutos.get("texto_vaga", ""))

    return {
        "status": "ok",
        "url_vaga": _limpar_texto(dados_brutos.get("url_vaga", "")),
        "titulo_vaga": _limpar_texto(dados_brutos.get("titulo_vaga", "")),
        "empresa": _limpar_texto(dados_brutos.get("empresa", "")),
        "localizacao": _normalizar_localizacao(dados_brutos.get("localizacao", "")),
        "modalidade": _normalizar_modalidade(
            _limpar_texto(dados_brutos.get("modalidade", "")),
            texto_vaga,
        ),
        "tipo_vaga": _normalizar_tipo_vaga(
            _limpar_texto(dados_brutos.get("tipo_vaga", "")),
            texto_vaga,
        ),
        "texto_vaga": texto_vaga,
        "fonte_vaga": "LinkedIn",
        "mensagem": _limpar_texto(dados_brutos.get("mensagem", "Normalizacao concluida com sucesso.")),
    }


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normaliza JSON bruto de vaga do LinkedIn.")
    parser.add_argument(
        "--input-json",
        help="JSON bruto da vaga. Se omitido, le da entrada padrao."
    )
    return parser


def main() -> int:
    args = criar_parser().parse_args()
    if args.input_json:
        dados = json.loads(args.input_json)
    else:
        import sys
        dados = json.loads(sys.stdin.read())

    resultado = normalizar_vaga(dados)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
