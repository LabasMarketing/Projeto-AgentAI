#!/usr/bin/env python3
"""
Coleta URLs de vagas em listagens do LinkedIn Jobs.

Responsabilidades:
- abrir uma pagina/listagem de vagas do LinkedIn
- coletar URLs unicas de vagas
- suportar filtros futuros de cargo, localizacao e modalidade
- detectar login/checkpoint/bloqueios comuns
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

from playwright.sync_api import Locator, Page, sync_playwright


@dataclass
class BuscaVagasLinkedInConfig:
    headless: bool = False
    profile_dir: str = "browser_profiles/linkedin"
    timeout_ms: int = 15000
    max_links: int = 25
    scroll_steps: int = 5
    search_url: Optional[str] = None
    cargo: Optional[str] = None
    localizacao: Optional[str] = None
    modalidade: Optional[str] = None
    candidatura_simplificada: bool = True


class BuscadorVagasLinkedIn:
    """Camada de coleta de links de vagas no LinkedIn."""

    def __init__(self, config: Optional[BuscaVagasLinkedInConfig] = None) -> None:
        self.config = config or BuscaVagasLinkedInConfig()
        self.project_root = Path(__file__).resolve().parents[2]
        self.profile_dir = self.project_root / self.config.profile_dir

    def buscar_urls(self) -> Dict[str, object]:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        search_url = self._resolve_search_url()

        print(f"[*] URL de busca usada: {search_url}")

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.config.headless,
            )

            try:
                page = context.new_page()
                page.set_default_timeout(self.config.timeout_ms)
                page.goto(search_url, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)

                bloqueio = self._detectar_bloqueio(page)
                if bloqueio:
                    return {
                        "status": "erro",
                        "search_url": search_url,
                        "links_encontrados": 0,
                        "vagas": [],
                        "mensagem": bloqueio,
                    }

                self._scrollar_listagem(page)
                vagas = self._extrair_links_unicos(page)

                print(f"[*] Total de links unicos encontrados: {len(vagas)}")

                return {
                    "status": "ok",
                    "search_url": search_url,
                    "links_encontrados": len(vagas),
                    "vagas": vagas,
                    "mensagem": "Coleta concluida com sucesso.",
                }
            finally:
                context.close()

    def _resolve_search_url(self) -> str:
        if self.config.search_url:
            return self.config.search_url

        params: Dict[str, str] = {}
        if self.config.cargo:
            params["keywords"] = self.config.cargo
        if self.config.localizacao:
            params["location"] = self.config.localizacao

        normalized_modalidade = (self.config.modalidade or "").strip().lower()
        if normalized_modalidade == "remoto":
            params["f_WT"] = "2"
        elif normalized_modalidade == "hibrido":
            params["f_WT"] = "3"
        elif normalized_modalidade == "presencial":
            params["f_WT"] = "1"

        if self.config.candidatura_simplificada:
            params["f_AL"] = "true"

        query = urlencode(params)
        base_url = "https://www.linkedin.com/jobs/search/"
        return f"{base_url}?{query}" if query else base_url

    def _detectar_bloqueio(self, page: Page) -> Optional[str]:
        url = page.url.lower()
        if "login" in url:
            return "LinkedIn redirecionou para login. Verifique a sessao salva no perfil do navegador."
        if "checkpoint" in url:
            return "LinkedIn redirecionou para checkpoint. A conta precisa de verificacao manual."

        body_text = self._safe_inner_text(page.locator("body"))
        body_text_lower = body_text.lower()

        sinais_bloqueio = [
            "quick security check",
            "verify your identity",
            "faça login",
            "faca login",
            "sign in",
            "captcha",
        ]

        for sinal in sinais_bloqueio:
            if sinal in body_text_lower:
                return f"LinkedIn exibiu tela de bloqueio/autenticacao: '{sinal}'."

        return None

    def _scrollar_listagem(self, page: Page) -> None:
        container = self._localizar_container_listagem(page)

        for _ in range(self.config.scroll_steps):
            try:
                if container is not None:
                    container.evaluate("(el) => { el.scrollTop = el.scrollTop + 1800; }")
                else:
                    page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1200)
            except Exception:
                break

    def _localizar_container_listagem(self, page: Page) -> Optional[Locator]:
        candidatos = [
            ".jobs-search-results-list",
            ".scaffold-layout__list-container",
            ".jobs-search-results-list__list",
            ".jobs-search-two-pane__wrapper",
        ]

        for seletor in candidatos:
            try:
                locator = page.locator(seletor).first
                if locator.count() > 0 and locator.is_visible():
                    return locator
            except Exception:
                continue
        return None

    def _extrair_links_unicos(self, page: Page) -> List[Dict[str, str]]:
        selectors = [
            "a[href*='/jobs/view/']",
            "a.job-card-container__link",
            "a[data-tracking-control-name*='public_jobs_jserp-result_search-card']",
        ]

        vagas: List[Dict[str, str]] = []
        vistos = set()

        for selector in selectors:
            locator = page.locator(selector)
            total = locator.count()

            for idx in range(total):
                try:
                    href = locator.nth(idx).get_attribute("href") or ""
                except Exception:
                    continue

                url_normalizada = self._normalizar_url_vaga(href)
                if not url_normalizada or url_normalizada in vistos:
                    continue

                vistos.add(url_normalizada)
                vagas.append({
                    "url_vaga": url_normalizada,
                    "fonte_vaga": "LinkedIn",
                })

                if len(vagas) >= self.config.max_links:
                    return vagas

        return vagas

    def _normalizar_url_vaga(self, href: str) -> Optional[str]:
        href = href.strip()
        if not href:
            return None
        if href.startswith("/jobs/view/"):
            href = f"https://www.linkedin.com{href}"
        if "/jobs/view/" not in href:
            return None
        return href.split("?")[0]

    def _safe_inner_text(self, locator: Locator) -> str:
        try:
            return locator.inner_text()
        except Exception:
            return ""


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Busca URLs de vagas no LinkedIn.")
    parser.add_argument("--search-url")
    parser.add_argument("--cargo")
    parser.add_argument("--localizacao")
    parser.add_argument("--modalidade")
    parser.add_argument(
        "--todas-as-vagas",
        action="store_true",
        help="Desabilita o filtro de candidatura simplificada (Easy Apply)."
    )
    parser.add_argument("--max-links", type=int, default=25)
    parser.add_argument("--scroll-steps", type=int, default=5)
    parser.add_argument("--headless", action="store_true")
    return parser


def main() -> int:
    args = criar_parser().parse_args()
    config = BuscaVagasLinkedInConfig(
        headless=args.headless,
        search_url=args.search_url,
        cargo=args.cargo,
        localizacao=args.localizacao,
        modalidade=args.modalidade,
        candidatura_simplificada=not args.todas_as_vagas,
        max_links=args.max_links,
        scroll_steps=args.scroll_steps,
    )
    buscador = BuscadorVagasLinkedIn(config)
    resultado = buscador.buscar_urls()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
