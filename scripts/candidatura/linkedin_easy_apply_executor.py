#!/usr/bin/env python3
"""
Executor para LinkedIn Easy Apply com leitura de campos por etapa.

Capacidades desta versão:
- abre a vaga e detecta Easy Apply
- percorre etapas do modal
- lê labels/títulos dos campos visíveis
- decide quando preencher, quando pular e quando parar para revisão
- trata upload de currículo
- faz scroll na etapa final para encontrar "Enviar candidatura"
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import Locator, Page, sync_playwright


@dataclass
class LinkedInExecResult:
    status: str
    easy_apply_detectado: bool
    modal_aberto: bool
    url_vaga: str
    titulo_vaga: Optional[str] = None
    empresa: Optional[str] = None
    observacoes: Optional[str] = None
    detalhes_fluxo: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "easy_apply_detectado": self.easy_apply_detectado,
            "modal_aberto": self.modal_aberto,
            "url_vaga": self.url_vaga,
            "titulo_vaga": self.titulo_vaga,
            "empresa": self.empresa,
            "observacoes": self.observacoes,
            "detalhes_fluxo": self.detalhes_fluxo or {},
        }


class LinkedInEasyApplyExecutor:
    def __init__(
        self,
        headless: bool = False,
        profile_dir: str = "browser_profiles/linkedin",
        timeout_ms: int = 15000,
    ) -> None:
        self.headless = headless
        self.profile_dir = Path(profile_dir)
        self.timeout_ms = timeout_ms
        self.project_root = Path(__file__).parent.parent
        self.candidate_profile = self._load_candidate_profile()
        self.resume_path = self._resolve_resume_path()

    def executar(self, vaga: Dict[str, Any]) -> Dict[str, Any]:
        url_vaga = vaga.get("url_vaga")
        if not url_vaga:
            return LinkedInExecResult(
                status="erro",
                easy_apply_detectado=False,
                modal_aberto=False,
                url_vaga="",
                observacoes="A vaga nao possui url_vaga.",
            ).to_dict()

        self.profile_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
            )

            try:
                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                page.goto(url_vaga, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)

                titulo_vaga = self._extrair_titulo(page)
                empresa = self._extrair_empresa(page)

                if "login" in page.url.lower() or "checkpoint" in page.url.lower():
                    return LinkedInExecResult(
                        status="login_necessario",
                        easy_apply_detectado=False,
                        modal_aberto=False,
                        url_vaga=url_vaga,
                        titulo_vaga=titulo_vaga,
                        empresa=empresa,
                        observacoes=(
                            "Sessao nao autenticada. Faca login manualmente uma vez "
                            "usando o perfil persistente e tente novamente."
                        ),
                    ).to_dict()

                botao_easy_apply = self._localizar_botao_easy_apply(page)
                if not botao_easy_apply:
                    return LinkedInExecResult(
                        status="nao_e_easy_apply",
                        easy_apply_detectado=False,
                        modal_aberto=False,
                        url_vaga=url_vaga,
                        titulo_vaga=titulo_vaga,
                        empresa=empresa,
                        observacoes="A vaga nao exibiu botao Easy Apply.",
                    ).to_dict()

                try:
                    botao_easy_apply.click()
                    page.wait_for_timeout(1500)
                except Exception as e:
                    return LinkedInExecResult(
                        status="erro_ao_clicar_easy_apply",
                        easy_apply_detectado=True,
                        modal_aberto=False,
                        url_vaga=url_vaga,
                        titulo_vaga=titulo_vaga,
                        empresa=empresa,
                        observacoes=f"Falha ao clicar no botao Easy Apply: {e}",
                    ).to_dict()

                modal_aberto = self._detectar_modal_candidatura(page)
                if not modal_aberto:
                    return LinkedInExecResult(
                        status="easy_apply_detectado_mas_modal_nao_abriu",
                        easy_apply_detectado=True,
                        modal_aberto=False,
                        url_vaga=url_vaga,
                        titulo_vaga=titulo_vaga,
                        empresa=empresa,
                        observacoes="O botao foi encontrado, mas o modal nao abriu como esperado.",
                    ).to_dict()

                fluxo = self._processar_fluxo_easy_apply(page)
                return LinkedInExecResult(
                    status=fluxo["status"],
                    easy_apply_detectado=True,
                    modal_aberto=True,
                    url_vaga=url_vaga,
                    titulo_vaga=titulo_vaga,
                    empresa=empresa,
                    observacoes=fluxo.get("observacoes"),
                    detalhes_fluxo=fluxo,
                ).to_dict()
            finally:
                context.close()

    def _load_candidate_profile(self) -> Dict[str, str]:
        defaults = {
            "email": os.getenv("LINKEDIN_EMAIL", "gabriellabarcadelbianco@gmail.com"),
            "country_code": os.getenv("LINKEDIN_COUNTRY_CODE", "Brasil (+55)"),
            "phone": os.getenv("LINKEDIN_PHONE", "11992893655"),
            "graduation_date": os.getenv("LINKEDIN_GRADUATION_DATE", "122027"),
            "salary_expectation": os.getenv("LINKEDIN_SALARY_EXPECTATION", "1700"),
            "worked_at_company_group": os.getenv("LINKEDIN_WORKED_AT_COMPANY_GROUP", "No"),
            "follow_company": os.getenv("LINKEDIN_FOLLOW_COMPANY", "false"),
        }

        perfil_path = self.project_root / "data" / "perfil.json"
        if not perfil_path.exists():
            return defaults

        try:
            with open(perfil_path, "r", encoding="utf-8") as f:
                perfil = json.load(f)
            defaults["name"] = perfil.get("informacoes_pessoais", {}).get("nome", "")
            defaults["course"] = perfil.get("formacao", {}).get("curso", "")
            defaults["institution"] = perfil.get("formacao", {}).get("instituicao", "")
        except Exception:
            pass

        return defaults

    def _resolve_resume_path(self) -> Optional[Path]:
        env_resume = os.getenv("LINKEDIN_RESUME_PATH")
        if env_resume:
            candidate = Path(env_resume)
            if not candidate.is_absolute():
                candidate = self.project_root / env_resume
            if candidate.exists():
                return candidate

        candidates = [
            self.project_root / "assets" / "CV_Gabriel_Labarca_Del_Bianco_compressed.pdf",
            self.project_root / "assets" / "curriculo.pdf",
            self.project_root / "curriculo.pdf",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _localizar_botao_easy_apply(self, page: Page):
        page.wait_for_timeout(3000)

        try:
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1500)
        except Exception:
            pass

        candidatos = [
            page.get_by_role("button", name="Easy Apply"),
            page.get_by_role("button", name="Continuar"),
            page.get_by_role("button", name="Candidatura simplificada"),
            page.get_by_role("button", name="Candidatura simplificada com IA"),
            page.get_by_role("link", name="Easy Apply"),
            page.get_by_role("link", name="Continuar"),
            page.get_by_role("link", name="Candidatura simplificada"),
            page.get_by_role("link", name="Candidatura simplificada com IA"),
            page.locator("button:has-text('Easy Apply')"),
            page.locator("button:has-text('Continuar')"),
            page.locator("button:has-text('Candidatura simplificada')"),
            page.locator("a:has-text('Easy Apply')"),
            page.locator("a:has-text('Continuar')"),
            page.locator("a:has-text('Candidatura simplificada')"),
            page.locator("a[href*='/apply/']"),
            page.locator("[aria-label*='Easy Apply']"),
            page.locator("[aria-label*='Continuar']"),
            page.locator("[aria-label*='Candidatura simplificada']"),
        ]

        for locator in candidatos:
            try:
                if locator.first.is_visible():
                    return locator.first
            except Exception:
                continue
        return None

    def _detectar_modal_candidatura(self, page: Page) -> bool:
        try:
            page.wait_for_selector("[role='dialog']", timeout=5000)
            return True
        except Exception:
            return False

    def _extrair_titulo(self, page: Page) -> Optional[str]:
        for seletor in ["h1", ".job-details-jobs-unified-top-card__job-title"]:
            try:
                el = page.locator(seletor).first
                if el.is_visible():
                    texto = el.inner_text().strip()
                    if texto:
                        return texto
            except Exception:
                continue
        return None

    def _extrair_empresa(self, page: Page) -> Optional[str]:
        for seletor in [
            ".job-details-jobs-unified-top-card__company-name a",
            ".job-details-jobs-unified-top-card__company-name",
        ]:
            try:
                el = page.locator(seletor).first
                if el.is_visible():
                    texto = el.inner_text().strip()
                    if texto:
                        return texto
            except Exception:
                continue
        return None

    def _processar_fluxo_easy_apply(self, page: Page) -> Dict[str, Any]:
        detalhes: Dict[str, Any] = {
            "etapas_processadas": 0,
            "campos_preenchidos": [],
            "campos_pulados": [],
            "campos_desconhecidos": [],
        }

        for step in range(10):
            print(f"Processando etapa {step + 1}")
            detalhes["etapas_processadas"] = step + 1
            page.wait_for_timeout(800)
            self._scrollar_modal_na_etapa(page, resetar_topo=True)

            etapa = self._preencher_campos_visiveis(page)
            detalhes["campos_preenchidos"].extend(etapa["campos_preenchidos"])
            detalhes["campos_pulados"].extend(etapa["campos_pulados"])
            detalhes["campos_desconhecidos"].extend(etapa["campos_desconhecidos"])
            self._scrollar_modal_na_etapa(page, resetar_topo=False)

            if etapa["campos_desconhecidos"]:
                return {
                    "status": "easy_apply_requer_revisao_manual",
                    "observacoes": (
                        "Foram encontrados campos obrigatorios sem regra segura de preenchimento. "
                        "Fluxo pausado para revisao manual."
                    ),
                    **detalhes,
                }

            if self._clicar_botao(page, ["Avancar", "Next"]):
                continue

            if self._clicar_botao(page, ["Revisar", "Review"]):
                continue

            if self._clicar_submit_final(page):
                return {
                    "status": "candidatura_enviada",
                    "observacoes": "Fluxo Easy Apply concluido e candidatura enviada.",
                    **detalhes,
                }

            return {
                "status": "easy_apply_pronto_para_revisao",
                "observacoes": "Nenhum botao adicional encontrado. Revise manualmente o modal.",
                **detalhes,
            }

        return {
            "status": "easy_apply_requer_revisao_manual",
            "observacoes": "Numero maximo de etapas atingido. Revise manualmente.",
            **detalhes,
        }

    def _preencher_campos_visiveis(self, page: Page) -> Dict[str, List[Dict[str, str]]]:
        resultado = {
            "campos_preenchidos": [],
            "campos_pulados": [],
            "campos_desconhecidos": [],
        }

        self._tratar_upload_curriculo(page, resultado)

        form_elements = page.locator("[data-test-form-element]")
        total = form_elements.count()

        for index in range(total):
            container = form_elements.nth(index)
            try:
                if not container.is_visible():
                    continue
            except Exception:
                continue

            label = self._extract_label_text(container)
            if not label:
                continue

            required = self._field_is_required(container, label)
            normalized_label = self._normalize(label)

            if self._try_fill_select(container, label, normalized_label, required, resultado):
                continue
            if self._try_fill_input(container, label, normalized_label, required, resultado):
                continue
            if self._try_fill_textarea(container, label, normalized_label, required, resultado):
                continue
            if self._try_fill_radio_or_checkbox(container, label, normalized_label, required, resultado):
                continue

            if required:
                resultado["campos_desconhecidos"].append(
                    {"label": label, "motivo": "campo_obrigatorio_sem_regra"}
                )
            else:
                resultado["campos_pulados"].append(
                    {"label": label, "motivo": "campo_opcional_sem_regra"}
                )

        return resultado

    def _tratar_upload_curriculo(self, page: Page, resultado: Dict[str, List[Dict[str, str]]]) -> None:
        upload_input = page.locator("input[type='file']")
        uploaded_resume = page.locator(".jobs-document-upload__uploaded-item, .jobs-document-upload-redesign-card")

        try:
            if uploaded_resume.count() > 0 and uploaded_resume.first.is_visible():
                resultado["campos_pulados"].append(
                    {"label": "Curriculo", "motivo": "curriculo_ja_carregado"}
                )
                return
        except Exception:
            pass

        try:
            if upload_input.count() == 0:
                return
        except Exception:
            return

        if not self.resume_path:
            resultado["campos_pulados"].append(
                {
                    "label": "Curriculo",
                    "motivo": "upload_pulado_para_usar_curriculo_ja_associado_no_linkedin",
                }
            )
            return

        try:
            upload_input.first.set_input_files(str(self.resume_path))
            page.wait_for_timeout(1500)
            resultado["campos_preenchidos"].append(
                {"label": "Curriculo", "valor": str(self.resume_path.name)}
            )
        except Exception as e:
            resultado["campos_pulados"].append(
                {
                    "label": "Curriculo",
                    "motivo": f"upload_pulado_falha_upload:{e}",
                }
            )

    def _try_fill_input(
        self,
        container: Locator,
        label: str,
        normalized_label: str,
        required: bool,
        resultado: Dict[str, List[Dict[str, str]]],
    ) -> bool:
        inputs = container.locator("input:not([type='file']):not([type='hidden'])")
        if inputs.count() == 0:
            return False

        field = inputs.first
        try:
            if not field.is_visible():
                return False
        except Exception:
            return False

        try:
            current_value = field.input_value().strip()
        except Exception:
            current_value = ""

        if current_value:
            resultado["campos_pulados"].append(
                {"label": label, "motivo": "ja_preenchido"}
            )
            return True

        answer = self._answer_for_label(normalized_label)
        if not answer:
            if required:
                resultado["campos_desconhecidos"].append(
                    {"label": label, "motivo": "input_obrigatorio_sem_resposta"}
                )
            else:
                resultado["campos_pulados"].append(
                    {"label": label, "motivo": "input_opcional_sem_resposta"}
                )
            return True

        try:
            field.fill(answer)
            resultado["campos_preenchidos"].append({"label": label, "valor": answer})
        except Exception as e:
            resultado["campos_desconhecidos"].append(
                {"label": label, "motivo": f"falha_fill:{e}"}
            )
        return True

    def _try_fill_select(
        self,
        container: Locator,
        label: str,
        normalized_label: str,
        required: bool,
        resultado: Dict[str, List[Dict[str, str]]],
    ) -> bool:
        selects = container.locator("select")
        if selects.count() == 0:
            return False

        select = selects.first
        try:
            if not select.is_visible():
                return False
        except Exception:
            return False

        current_text = self._selected_option_text(select)
        if current_text and "selecionar" not in self._normalize(current_text):
            resultado["campos_pulados"].append(
                {"label": label, "motivo": "select_ja_preenchido"}
            )
            return True

        answer = self._answer_for_label(normalized_label)
        options = self._collect_select_options(select)

        if answer:
            matched = self._find_best_option(options, answer)
            if matched:
                try:
                    select.select_option(value=matched[0])
                    resultado["campos_preenchidos"].append({"label": label, "valor": matched[1]})
                    return True
                except Exception:
                    try:
                        select.select_option(label=matched[1])
                        resultado["campos_preenchidos"].append({"label": label, "valor": matched[1]})
                        return True
                    except Exception:
                        pass

        fallback = self._first_non_placeholder_option(options)
        if fallback and not required:
            try:
                select.select_option(value=fallback[0])
                resultado["campos_preenchidos"].append({"label": label, "valor": fallback[1]})
            except Exception:
                resultado["campos_pulados"].append({"label": label, "motivo": "nao_foi_possivel_preencher_select"})
            return True

        if required:
            resultado["campos_desconhecidos"].append(
                {"label": label, "motivo": "select_obrigatorio_sem_resposta"}
            )
        else:
            resultado["campos_pulados"].append(
                {"label": label, "motivo": "select_opcional_sem_resposta"}
            )
        return True

    def _try_fill_textarea(
        self,
        container: Locator,
        label: str,
        normalized_label: str,
        required: bool,
        resultado: Dict[str, List[Dict[str, str]]],
    ) -> bool:
        textareas = container.locator("textarea")
        if textareas.count() == 0:
            return False

        textarea = textareas.first
        try:
            if not textarea.is_visible():
                return False
        except Exception:
            return False

        try:
            current_value = textarea.input_value().strip()
        except Exception:
            current_value = ""

        if current_value:
            resultado["campos_pulados"].append({"label": label, "motivo": "textarea_ja_preenchido"})
            return True

        answer = self._answer_for_label(normalized_label)
        if not answer:
            if required:
                resultado["campos_desconhecidos"].append(
                    {"label": label, "motivo": "textarea_obrigatorio_sem_resposta"}
                )
            else:
                resultado["campos_pulados"].append(
                    {"label": label, "motivo": "textarea_opcional_sem_resposta"}
                )
            return True

        try:
            textarea.fill(answer)
            resultado["campos_preenchidos"].append({"label": label, "valor": answer})
        except Exception as e:
            resultado["campos_desconhecidos"].append(
                {"label": label, "motivo": f"falha_textarea:{e}"}
            )
        return True

    def _try_fill_radio_or_checkbox(
        self,
        container: Locator,
        label: str,
        normalized_label: str,
        required: bool,
        resultado: Dict[str, List[Dict[str, str]]],
    ) -> bool:
        radios = container.locator("input[type='radio']")
        checkboxes = container.locator("input[type='checkbox']")
        if radios.count() == 0 and checkboxes.count() == 0:
            return False

        answer = self._answer_for_label(normalized_label)
        if not answer and required:
            resultado["campos_desconhecidos"].append(
                {"label": label, "motivo": "escolha_obrigatoria_sem_resposta"}
            )
            return True
        if not answer:
            resultado["campos_pulados"].append(
                {"label": label, "motivo": "escolha_opcional_sem_resposta"}
            )
            return True

        options = container.locator("label, span[role='button'], div[role='radio']")
        total = options.count()
        target = self._normalize(answer)

        for idx in range(total):
            option = options.nth(idx)
            try:
                text = option.inner_text().strip()
            except Exception:
                continue
            if target in self._normalize(text):
                try:
                    option.click()
                    resultado["campos_preenchidos"].append({"label": label, "valor": text})
                    return True
                except Exception:
                    continue

        if required:
            resultado["campos_desconhecidos"].append(
                {"label": label, "motivo": "nao_encontrou_opcao_correspondente"}
            )
        else:
            resultado["campos_pulados"].append(
                {"label": label, "motivo": "nao_encontrou_opcao_correspondente"}
            )
        return True

    def _click_modal_button(self, page: Page, keywords: List[str]) -> bool:
        dialog = page.locator("[role='dialog']").last
        scroll_targets = [
            dialog.locator(".jobs-easy-apply-modal__content"),
            dialog.locator("div[tabindex='-1']").first,
            dialog,
        ]

        for _ in range(8):
            button = self._find_button_by_keywords(dialog, keywords)
            if button:
                try:
                    button.scroll_into_view_if_needed()
                except Exception:
                    pass
                page.wait_for_timeout(300)
                button.click(force=True)
                page.wait_for_timeout(1000)
                return True

            self._scrollar_modal_na_etapa(page, resetar_topo=False)
            for target in scroll_targets:
                try:
                    if target.count() > 0:
                        target.first.evaluate("(el) => { el.scrollTop = el.scrollTop + 500; }")
                        page.wait_for_timeout(300)
                except Exception:
                    continue

        return False

    def _scrollar_modal_na_etapa(self, page: Page, resetar_topo: bool = False) -> None:
        dialog = page.locator("[role='dialog']").last
        scroll_targets = [
            dialog.locator(".jobs-easy-apply-modal__content"),
            dialog.locator("div[tabindex='-1']").first,
            dialog,
        ]

        for target in scroll_targets:
            try:
                if target.count() == 0:
                    continue

                container = target.first
                if not container.is_visible():
                    continue

                if resetar_topo:
                    container.evaluate("(el) => { el.scrollTop = 0; }")
                    page.wait_for_timeout(200)

                for offset in [350, 700, 1100]:
                    container.evaluate(f"(el) => {{ el.scrollTop = el.scrollTop + {offset}; }}")
                    page.wait_for_timeout(250)

                return
            except Exception:
                continue

    def _clicar_botao(self, page: Page, textos: List[str]) -> bool:
        return self._click_modal_button(page, textos)

    def _clicar_submit_final(self, page: Page) -> bool:
        return self._click_modal_button(page, ["Enviar candidatura", "Submit application"])

    def _find_button_by_keywords(self, scope: Locator, keywords: List[str]) -> Optional[Locator]:
        buttons = scope.locator("button")
        total = buttons.count()
        normalized_keywords = [self._normalize(k) for k in keywords]

        for i in range(total):
            btn = buttons.nth(i)
            try:
                if not btn.is_visible():
                    continue
                text = btn.inner_text().strip()
                aria = btn.get_attribute("aria-label") or ""
                haystack = self._normalize(f"{text} {aria}")
                if any(keyword in haystack for keyword in normalized_keywords):
                    return btn
            except Exception:
                continue
        return None

    def _extract_label_text(self, container: Locator) -> str:
        label_candidates = [
            "label",
            "span[data-test-single-line-text-form-title]",
            "span[data-test-text-entity-list-form-title]",
            ".fb-dash-form-element__label",
            ".jobs-document-upload__title--is-required",
            ".jobs-document-upload-redesign-card__title--is-required",
        ]

        for selector in label_candidates:
            try:
                loc = container.locator(selector).first
                if loc.count() > 0 and loc.is_visible():
                    text = re.sub(r"\s+", " ", loc.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue

        try:
            text = re.sub(r"\s+", " ", container.inner_text()).strip()
            if text:
                return text.split("\n")[0]
        except Exception:
            pass
        return ""

    def _field_is_required(self, container: Locator, label: str) -> bool:
        if "*" in label:
            return True
        try:
            required_nodes = container.locator("[required], .fb-dash-form-element__label-title--is-required")
            return required_nodes.count() > 0
        except Exception:
            return False

    def _selected_option_text(self, select: Locator) -> str:
        try:
            return select.locator("option:checked").first.inner_text().strip()
        except Exception:
            return ""

    def _collect_select_options(self, select: Locator) -> List[Tuple[str, str]]:
        options = select.locator("option")
        items: List[Tuple[str, str]] = []
        for idx in range(options.count()):
            opt = options.nth(idx)
            try:
                items.append(((opt.get_attribute("value") or "").strip(), opt.inner_text().strip()))
            except Exception:
                continue
        return items

    def _first_non_placeholder_option(self, options: List[Tuple[str, str]]) -> Optional[Tuple[str, str]]:
        for value, label in options:
            normalized = self._normalize(label)
            if not value:
                continue
            if "selecionar" in normalized or "select" in normalized:
                continue
            return value, label
        return None

    def _find_best_option(self, options: List[Tuple[str, str]], answer: str) -> Optional[Tuple[str, str]]:
        target = self._normalize(answer)
        for value, label in options:
            normalized_label = self._normalize(label)
            if target == normalized_label or target in normalized_label or normalized_label in target:
                return value, label
        return None

    def _answer_for_label(self, normalized_label: str) -> Optional[str]:
        rules = [
            (["e mail", "email"], self.candidate_profile.get("email")),
            (["codigo do pais", "codigo do país", "country code"], self.candidate_profile.get("country_code")),
            (["numero de celular", "número de celular", "telefone", "phone"], self.candidate_profile.get("phone")),
            (
                ["qual o mes e o ano de conclusao da sua faculdade", "qual o mes e o ano de conclusao"],
                self.candidate_profile.get("graduation_date"),
            ),
            (
                ["pretensao salarial", "pretensão salarial", "salary expectation", "salary"],
                self.candidate_profile.get("salary_expectation"),
            ),
            (
                [
                    "voce ja atuou em alguma empresa do grupo deutsche telekom",
                    "ja atuou em alguma empresa do grupo deutsche telekom",
                    "t systems",
                    "t-systems",
                    "deutsche telekom",
                ],
                self.candidate_profile.get("worked_at_company_group"),
            ),
            (
                ["siga a empresa", "follow the company"],
                "Sim" if self.candidate_profile.get("follow_company", "").lower() == "true" else "Nao",
            ),
        ]

        for patterns, value in rules:
            if any(pattern in normalized_label for pattern in patterns):
                return value
        return None

    def _normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
