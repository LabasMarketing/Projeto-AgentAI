#!/usr/bin/env python3
"""
Extrai dados visiveis de uma vaga individual do LinkedIn.

Responsabilidades:
- abrir uma vaga individual do LinkedIn
- extrair os principais campos visiveis da pagina
- detectar login/checkpoint/bloqueios comuns
- retornar estrutura com status e campos auxiliares para debug
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Locator, Page, sync_playwright


@dataclass
class ExtracaoVagaConfig:
    headless: bool = False
    profile_dir: str = "browser_profiles/linkedin"
    timeout_ms: int = 15000


class ExtratorDadosVagaLinkedIn:
    """Extrai dados brutos de uma vaga do LinkedIn."""

    def __init__(self, config: Optional[ExtracaoVagaConfig] = None) -> None:
        self.config = config or ExtracaoVagaConfig()
        self.project_root = Path(__file__).resolve().parents[2]
        self.profile_dir = self.project_root / self.config.profile_dir

    def extrair(self, url_vaga: str) -> Dict[str, Any]:
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.config.headless,
            )

            try:
                page = context.new_page()
                page.set_default_timeout(self.config.timeout_ms)
                page.goto(url_vaga, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                bloqueio = self._detectar_bloqueio(page)
                if bloqueio:
                    return {
                        "status": "erro",
                        "url_vaga": url_vaga,
                        "titulo_vaga": "",
                        "empresa": "",
                        "localizacao": "",
                        "modalidade": "",
                        "tipo_vaga": "",
                        "texto_vaga": "",
                        "texto_topo_vaga": "",
                        "texto_total_pagina": self._limpar_texto(self._texto_total(page)),
                        "mensagem": bloqueio,
                    }

                self._expandir_descricao(page)

                dados_topo = self._extrair_dados_topo(page)
                titulo_vaga = dados_topo["titulo_vaga"]
                empresa = dados_topo["empresa"]
                texto_topo_vaga = self._extrair_texto_topo_vaga(page)
                texto_total_pagina = self._limpar_texto(self._texto_total(page))
                texto_vaga = self._extrair_texto_vaga(page, texto_total_pagina)

                if not titulo_vaga and not texto_vaga:
                    return {
                        "status": "erro",
                        "url_vaga": url_vaga,
                        "titulo_vaga": "",
                        "empresa": empresa,
                        "localizacao": "",
                        "modalidade": "",
                        "tipo_vaga": "",
                        "texto_vaga": "",
                        "texto_topo_vaga": texto_topo_vaga,
                        "texto_total_pagina": texto_total_pagina,
                        "mensagem": "Nao foi possivel extrair titulo_vaga nem texto_vaga da pagina.",
                    }

                return {
                    "status": "ok",
                    "url_vaga": url_vaga,
                    "titulo_vaga": titulo_vaga,
                    "empresa": empresa,
                    "localizacao": dados_topo["localizacao"] or self._extrair_localizacao(page, texto_topo_vaga),
                    "modalidade": self._inferir_modalidade(texto_total_pagina),
                    "tipo_vaga": self._inferir_tipo_vaga(texto_total_pagina),
                    "texto_vaga": texto_vaga,
                    "texto_topo_vaga": texto_topo_vaga,
                    "texto_total_pagina": texto_total_pagina,
                    "mensagem": "Extracao concluida com sucesso.",
                }
            finally:
                context.close()

    def _extrair_dados_topo(self, page: Page) -> Dict[str, str]:
        titulo_vaga = ""
        empresa = ""
        localizacao = ""
        estrategia_titulo = "nao_encontrado"
        estrategia_empresa = "nao_encontrado"
        estrategia_localizacao = "nao_encontrado"

        empresa = self._extrair_empresa_por_aria_label(page)
        if empresa:
            estrategia_empresa = "aria-label"

        texto_total = self._limpar_texto(self._texto_total(page))
        trecho_topo = self._extrair_trecho_antes_de_sobre_vaga(texto_total)
        dados_textuais = self._extrair_titulo_localizacao_por_texto(trecho_topo, empresa)

        titulo_vaga = dados_textuais["titulo_vaga"]
        localizacao = dados_textuais["localizacao"]

        if titulo_vaga:
            estrategia_titulo = "heuristica_texto"
            print("[*] titulo_vaga via heuristica_texto")

        if localizacao:
            estrategia_localizacao = "heuristica_texto"
            print("[*] localizacao via heuristica_texto")

        topo = self._localizar_bloco_topo(page)

        if topo is not None and not empresa:
            empresa = self._extrair_empresa_do_topo(topo, titulo_vaga)
            if empresa:
                estrategia_empresa = "fallback_topo"

        if topo is not None and not titulo_vaga:
            titulo_vaga = self._extrair_titulo_do_topo(topo)
            if titulo_vaga:
                estrategia_titulo = "fallback_topo"

        if topo is not None and not localizacao:
            localizacao = self._extrair_localizacao_do_topo(topo, titulo_vaga, empresa)
            if localizacao:
                estrategia_localizacao = "fallback_topo"

        if not titulo_vaga:
            titulo_vaga = self._extrair_primeiro_texto(
                page,
                [
                    "h1",
                    ".job-details-jobs-unified-top-card__job-title",
                ],
            )
            if titulo_vaga:
                estrategia_titulo = "fallback_selector"

        if not empresa:
            empresa = self._extrair_primeiro_texto(
                page,
                [
                    ".job-details-jobs-unified-top-card__company-name a",
                    ".job-details-jobs-unified-top-card__company-name",
                ],
            )
            if empresa:
                estrategia_empresa = "fallback_selector"

        if not localizacao:
            localizacao = self._extrair_localizacao_fallback(page)
            if localizacao:
                estrategia_localizacao = "fallback_selector"

        print(f"[*] Estrategia titulo_vaga: {estrategia_titulo}")
        print(f"[*] Estrategia empresa: {estrategia_empresa}")
        print(f"[*] Estrategia localizacao: {estrategia_localizacao}")

        return {
            "titulo_vaga": titulo_vaga,
            "empresa": empresa,
            "localizacao": localizacao,
        }

    def _extrair_trecho_antes_de_sobre_vaga(self, texto_total: str) -> str:
        texto = self._limpar_texto(texto_total)
        marcadores = ["Sobre a vaga", "About the job"]

        corte = len(texto)
        texto_lower = texto.lower()
        for marcador in marcadores:
            idx = texto_lower.find(marcador.lower())
            if idx != -1:
                corte = min(corte, idx)

        trecho = texto[:corte]

        ruidos = [
            "Exibir tudo",
            "Pessoas que você pode contatar",
            "Pessoas que voce pode contatar",
            "Experimente Premium",
            "Experimente o Premium",
            "Candidate-se",
            "Salvar",
            "Início",
            "Inicio",
            "Minha rede",
            "Vagas",
            "Mensagens",
            "Notificações",
            "Notificacoes",
        ]

        for ruido in ruidos:
            trecho = trecho.replace(ruido, "\n")

        trecho = re.sub(r"\s{2,}", " ", trecho)
        trecho = re.sub(r"(?:\n\s*){2,}", "\n", trecho)
        return trecho.strip()

    def _extrair_titulo_localizacao_por_texto(self, trecho: str, empresa: str) -> Dict[str, str]:
        linhas = [
            self._limpar_texto(linha)
            for linha in re.split(r"[\n\r]+|(?<=\.)\s{2,}", trecho)
        ]
        linhas = [linha for linha in linhas if linha and self._linha_relevante(linha)]

        titulo_vaga = ""
        localizacao = ""

        for idx, linha in enumerate(linhas):
            if self._parece_titulo_por_texto(linha, empresa):
                titulo_vaga = linha
                for proxima in linhas[idx + 1:]:
                    if self._parece_localizacao_por_texto(proxima):
                        localizacao = proxima
                        break
                break

        return {
            "titulo_vaga": titulo_vaga,
            "localizacao": localizacao,
        }

    def _linha_relevante(self, linha: str) -> bool:
        linha_lower = linha.lower()
        bloqueios = [
            "exibir tudo",
            "pessoas que você pode contatar",
            "pessoas que voce pode contatar",
            "experimente premium",
            "experimente o premium",
            "candidate se",
            "candidate-se",
            "salvar",
            "início",
            "inicio",
            "minha rede",
            "mensagens",
            "notificações",
            "notificacoes",
            "vagas",
        ]
        return not any(bloqueio in linha_lower for bloqueio in bloqueios)

    def _parece_titulo_por_texto(self, linha: str, empresa: str) -> bool:
        linha_lower = linha.lower()
        empresa_lower = (empresa or "").lower()
        if not linha or linha_lower == empresa_lower:
            return False
        if "," in linha:
            return False
        if len(linha) < 10 or len(linha) > 140:
            return False
        if any(token in linha_lower for token in ["promovida", "há ", "ha ", "candidatos", "brasil"]):
            return False
        return True

    def _parece_localizacao_por_texto(self, linha: str) -> bool:
        linha_lower = linha.lower()
        if any(token in linha_lower for token in ["promovida", "há ", "ha ", "candidatos"]):
            return False
        return "," in linha or "brasil" in linha_lower or "região" in linha_lower or "regiao" in linha_lower

    def _localizar_bloco_topo(self, page: Page) -> Optional[Locator]:
        sobre_vaga = self._localizar_secao_sobre_vaga(page)
        if sobre_vaga is not None:
            for xpath in [
                "xpath=preceding::*[self::section or self::div][1]",
                "xpath=preceding::*[self::section or self::div][2]",
                "xpath=preceding::*[self::section or self::div][3]",
                "xpath=ancestor::*[self::section or self::div][1]/preceding-sibling::*[self::section or self::div][1]",
                "xpath=ancestor::*[self::section or self::div][2]/preceding-sibling::*[self::section or self::div][1]",
            ]:
                try:
                    candidato = sobre_vaga.locator(xpath).first
                    if candidato.count() > 0 and candidato.is_visible():
                        texto = self._limpar_texto(candidato.inner_text())
                        if self._parece_bloco_topo_vaga(texto):
                            print(f"[*] Container topo escolhido: ancora_sobre_vaga -> {xpath}")
                            return candidato
                except Exception:
                    continue

        try:
            h1 = page.locator("h1").first
            if h1.count() > 0 and h1.is_visible():
                for xpath in [
                    "xpath=ancestor::*[self::header or self::section or self::div][1]",
                    "xpath=ancestor::*[self::header or self::section or self::div][2]",
                    "xpath=ancestor::*[self::header or self::section or self::div][3]",
                ]:
                    candidato = h1.locator(xpath).first
                    if candidato.count() > 0 and candidato.is_visible():
                        try:
                            texto = self._limpar_texto(candidato.inner_text())
                        except Exception:
                            texto = ""
                        if self._parece_bloco_topo_vaga(texto):
                            print(f"[*] Container topo escolhido: ancora_h1 -> {xpath}")
                            return candidato
        except Exception:
            pass

        candidatos = [
            "main section",
            "main div",
            "[role='main'] section",
            "[role='main'] div",
            "header",
            "main",
            "article",
            "[role='main']",
            ".job-details-jobs-unified-top-card__content",
        ]
        for seletor in candidatos:
            try:
                locator = page.locator(seletor).first
                if locator.count() > 0 and locator.is_visible():
                    texto = self._limpar_texto(locator.inner_text())
                    if self._parece_bloco_topo_vaga(texto):
                        print(f"[*] Container topo escolhido: fallback -> {seletor}")
                        return locator
            except Exception:
                continue
        return None

    def _localizar_secao_sobre_vaga(self, page: Page) -> Optional[Locator]:
        candidatos = [
            page.get_by_text(re.compile(r"^Sobre a vaga$", re.I)),
            page.get_by_text(re.compile(r"^About the job$", re.I)),
            page.locator("h2:has-text('Sobre a vaga')"),
            page.locator("h2:has-text('About the job')"),
            page.locator("span:has-text('Sobre a vaga')"),
            page.locator("span:has-text('About the job')"),
        ]

        for locator in candidatos:
            try:
                if locator.count() > 0 and locator.first.is_visible():
                    return locator.first
            except Exception:
                continue
        return None

    def _extrair_titulo_do_topo(self, topo: Locator) -> str:
        try:
            elementos = topo.locator("p")
            for idx in range(min(elementos.count(), 6)):
                texto = self._limpar_texto(elementos.nth(idx).inner_text())
                if self._parece_titulo_vaga(texto):
                    return texto
        except Exception:
            pass

        for seletor in ["h1", "span"]:
            try:
                elementos = topo.locator(seletor)
                for idx in range(min(elementos.count(), 5)):
                    texto = self._limpar_texto(elementos.nth(idx).inner_text())
                    if self._parece_titulo_vaga(texto):
                        return texto
            except Exception:
                continue
        return ""

    def _extrair_empresa_do_topo(self, topo: Locator, titulo_vaga: str) -> str:
        try:
            links = topo.locator("a")
            for idx in range(min(links.count(), 10)):
                texto = self._limpar_texto(links.nth(idx).inner_text())
                if self._parece_empresa(texto, titulo_vaga):
                    return texto
        except Exception:
            pass

        for seletor in ["span", "p"]:
            try:
                elementos = topo.locator(seletor)
                for idx in range(min(elementos.count(), 10)):
                    texto = self._limpar_texto(elementos.nth(idx).inner_text())
                    if self._parece_empresa(texto, titulo_vaga):
                        return texto
            except Exception:
                continue
        return ""

    def _extrair_localizacao_do_topo(self, topo: Locator, titulo_vaga: str, empresa: str) -> str:
        try:
            paragrafos = topo.locator("p")
            for idx in range(min(paragrafos.count(), 6)):
                paragrafo = paragrafos.nth(idx)
                texto_paragrafo = self._limpar_texto(paragrafo.inner_text())

                if idx == 0 and self._parece_titulo_vaga(texto_paragrafo):
                    continue

                spans = paragrafo.locator("span")
                for span_idx in range(min(spans.count(), 5)):
                    texto_span = self._limpar_texto(spans.nth(span_idx).inner_text())
                    if self._parece_localizacao(texto_span, titulo_vaga, empresa):
                        return self._normalizar_localizacao(texto_span)

                if self._parece_localizacao(texto_paragrafo, titulo_vaga, empresa):
                    return self._normalizar_localizacao(texto_paragrafo)
        except Exception:
            pass

        for seletor in ["span", "div"]:
            try:
                elementos = topo.locator(seletor)
                for idx in range(min(elementos.count(), 10)):
                    texto = self._limpar_texto(elementos.nth(idx).inner_text())
                    if self._parece_localizacao(texto, titulo_vaga, empresa):
                        return self._normalizar_localizacao(texto)
            except Exception:
                continue
        return ""

    def _extrair_empresa_por_aria_label(self, page: Page) -> str:
        try:
            elementos = page.locator("[aria-label^='Empresa ']")
            for idx in range(min(elementos.count(), 5)):
                texto = self._limpar_texto(elementos.nth(idx).inner_text())
                aria_label = self._limpar_texto(elementos.nth(idx).get_attribute("aria-label") or "")
                valor = texto or re.sub(r"^Empresa\s+", "", aria_label, flags=re.I).strip()
                if valor:
                    return re.sub(r"^Empresa\s+", "", valor, flags=re.I).strip()
        except Exception:
            pass
        return ""

    def _parece_titulo_vaga(self, texto: str) -> bool:
        if not texto:
            return False
        if len(texto) < 5 or len(texto) > 160:
            return False
        texto_lower = texto.lower()
        bloqueios = [
            "sign in",
            "faça login",
            "faca login",
            "linkedin",
            "candidatura simplificada",
            "experimente o premium",
            "premium por",
            "início minha rede vagas",
            "inicio minha rede vagas",
            "vagas",
            "início",
            "inicio",
        ]
        if any(texto_lower == bloqueio for bloqueio in bloqueios):
            return False
        if any(bloqueio in texto_lower for bloqueio in bloqueios[:8]):
            return False
        return True

    def _parece_empresa(self, texto: str, titulo_vaga: str) -> bool:
        if not texto or texto == titulo_vaga:
            return False
        if len(texto) < 2 or len(texto) > 120:
            return False
        texto_lower = texto.lower()
        bloqueios = [
            "seguir",
            "followers",
            "conexões",
            "conexoes",
            "promovida",
            "há ",
            "ha ",
            "vagas",
            "início",
            "inicio",
            "mensagens",
            "premium",
        ]
        return not any(bloqueio in texto_lower for bloqueio in bloqueios)

    def _parece_localizacao(self, texto: str, titulo_vaga: str, empresa: str) -> bool:
        if not texto or texto in {titulo_vaga, empresa}:
            return False
        if len(texto) < 4 or len(texto) > 120:
            return False
        texto_lower = texto.lower()
        if (
            "promovida" in texto_lower
            or "candidatos" in texto_lower
            or "há " in texto_lower
            or "ha " in texto_lower
            or "início minha rede" in texto_lower
            or "inicio minha rede" in texto_lower
            or "premium" in texto_lower
        ):
            return False
        if "," in texto or "região" in texto_lower or "regiao" in texto_lower or "brasil" in texto_lower:
            return True
        return False

    def _parece_bloco_topo_vaga(self, texto: str) -> bool:
        texto = self._limpar_texto(texto)
        if not texto:
            return False

        texto_lower = texto.lower()
        sinais_ruins = [
            "experimente o premium",
            "início minha rede vagas mensagens",
            "inicio minha rede vagas mensagens",
            "ver perfil",
            "anúncio",
            "anuncio",
            "pessoas que você pode contatar",
            "pessoas que voce pode contatar",
        ]
        if any(sinal in texto_lower for sinal in sinais_ruins):
            return False

        sinais_bons = [
            "sobre a vaga",
            "candidatura simplificada",
            "há ",
            "ha ",
            "candidatos",
            "brasil",
        ]

        has_h1_like = any(len(linha.strip()) > 5 and len(linha.strip()) < 140 for linha in texto.split("\n"))
        has_good_signal = any(sinal in texto_lower for sinal in sinais_bons)
        return has_h1_like or has_good_signal

    def _detectar_bloqueio(self, page: Page) -> Optional[str]:
        url = page.url.lower()
        if "login" in url:
            return "LinkedIn redirecionou para login. Verifique a sessao salva no perfil do navegador."
        if "checkpoint" in url:
            return "LinkedIn redirecionou para checkpoint. A conta precisa de verificacao manual."

        body_text = self._texto_total(page).lower()
        sinais_bloqueio = [
            "quick security check",
            "verify your identity",
            "faça login",
            "faca login",
            "sign in",
            "captcha",
        ]
        for sinal in sinais_bloqueio:
            if sinal in body_text:
                return f"LinkedIn exibiu tela de bloqueio/autenticacao: '{sinal}'."
        return None

    def _expandir_descricao(self, page: Page) -> None:
        candidatos = [
            page.get_by_role("button", name=re.compile("see more", re.I)),
            page.get_by_role("button", name=re.compile("ver mais", re.I)),
            page.locator("button:has-text('See more')"),
            page.locator("button:has-text('Ver mais')"),
        ]

        for locator in candidatos:
            try:
                if locator.count() > 0 and locator.first.is_visible():
                    locator.first.click()
                    page.wait_for_timeout(800)
                    return
            except Exception:
                continue

    def _extrair_primeiro_texto(self, page: Page, selectors: List[str]) -> str:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0 and locator.is_visible():
                    texto = self._limpar_texto(locator.inner_text())
                    if texto:
                        return texto
            except Exception:
                continue
        return ""

    def _extrair_texto_topo_vaga(self, page: Page) -> str:
        topo = self._localizar_bloco_topo(page)
        if topo is not None:
            try:
                texto = self._limpar_texto(topo.inner_text())
                if texto:
                    return texto
            except Exception:
                pass

        candidatos = [
            ".job-details-jobs-unified-top-card__primary-description-container",
            ".job-details-jobs-unified-top-card__primary-description",
            ".job-details-jobs-unified-top-card__content",
        ]
        for selector in candidatos:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0 and locator.is_visible():
                    texto = self._limpar_texto(locator.inner_text())
                    if texto:
                        return texto
            except Exception:
                continue
        return ""

    def _extrair_localizacao(self, page: Page, texto_topo_vaga: str) -> str:
        localizacao_fallback = self._extrair_localizacao_fallback(page)
        if localizacao_fallback:
            return localizacao_fallback

        return self._normalizar_localizacao(texto_topo_vaga)

    def _extrair_localizacao_fallback(self, page: Page) -> str:
        candidatos = [
            ".job-details-jobs-unified-top-card__primary-description-container",
            ".job-details-jobs-unified-top-card__primary-description",
            ".t-black--light.mt2",
        ]
        for selector in candidatos:
            try:
                texto = self._extrair_primeiro_texto(page, [selector])
                localizacao = self._normalizar_localizacao(texto)
                if localizacao:
                    return localizacao
            except Exception:
                continue
        return ""

    def _normalizar_localizacao(self, texto: str) -> str:
        texto = self._limpar_texto(texto)
        if not texto:
            return ""

        separadores = ["·", "•", "|"]
        partes = [texto]
        for separador in separadores:
            novas_partes: List[str] = []
            for parte in partes:
                novas_partes.extend([item.strip() for item in parte.split(separador) if item.strip()])
            partes = novas_partes

        candidatos = [parte for parte in partes if any(char.isdigit() for char in parte) is False]
        return candidatos[0] if candidatos else partes[0]

    def _inferir_modalidade(self, texto_total: str) -> str:
        texto_normalizado = texto_total.lower()
        if "híbrido" in texto_normalizado or "hibrido" in texto_normalizado or "hybrid" in texto_normalizado:
            return "Híbrido"
        if "remoto" in texto_normalizado or "remote" in texto_normalizado:
            return "Remoto"
        if "presencial" in texto_normalizado or "on-site" in texto_normalizado or "onsite" in texto_normalizado:
            return "Presencial"
        return ""

    def _inferir_tipo_vaga(self, texto_total: str) -> str:
        texto_total = texto_total.lower()
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
        ]
        for termo, tipo in regras:
            if termo in texto_total:
                return tipo
        return ""

    def _limpar_texto_vaga(self, texto_total: str) -> str:
        if not texto_total:
            return ""

        inicio = texto_total.find("Sobre a vaga")

        if inicio == -1:
            return texto_total

        texto = texto_total[inicio:]

        marcadores_fim = [
            "Sobre a empresa",
            "Mais vagas",
            "Ver mais vagas",
            "Seja mais eficiente",
            "Procurando um talento",
            "LinkedIn Corporation",
        ]

        fim = len(texto)
        for marcador in marcadores_fim:
            idx = texto.find(marcador)
            if idx != -1:
                fim = min(fim, idx)

        texto = texto[:fim]

        return texto.strip()

    def _extrair_texto_vaga(self, page: Page, texto_total_pagina: str) -> str:
        texto_limpo = self._limpar_texto_vaga(texto_total_pagina)

        print("[*] Texto da vaga limpo extraído")

        return texto_limpo

    def _texto_total(self, page: Page) -> str:
        try:
            return page.locator("body").inner_text()
        except Exception:
            return ""

    def _limpar_texto(self, texto: str) -> str:
        return re.sub(r"\s+", " ", texto or "").strip()


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extrai dados de uma vaga do LinkedIn.")
    parser.add_argument("url_vaga")
    parser.add_argument("--headless", action="store_true")
    return parser


def main() -> int:
    args = criar_parser().parse_args()
    extrator = ExtratorDadosVagaLinkedIn(ExtracaoVagaConfig(headless=args.headless))
    resultado = extrator.extrair(args.url_vaga)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
