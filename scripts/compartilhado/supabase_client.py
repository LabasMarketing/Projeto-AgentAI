#!/usr/bin/env python3
"""
Cliente Supabase para integração com banco de dados.
Responsável por salvar resultados de análise de vagas na tabela vagas_analisadas.
"""

import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError(
        "Biblioteca 'supabase' não instalada. "
        "Execute: pip install supabase"
    )


class SupabaseClient:
    """Cliente para integração com Supabase."""
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        """
        Inicializa o cliente Supabase.
        
        Args:
            supabase_url: URL do projeto Supabase (ou env var SUPABASE_URL)
            supabase_key: Chave de API do Supabase (ou env var SUPABASE_KEY)
            
        Raises:
            ValueError: Se URL ou chave não forem fornecidas ou configuradas
        """
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url:
            raise ValueError(
                "SUPABASE_URL não fornecida. "
                "Configure via parâmetro ou variável de ambiente."
            )
        if not self.supabase_key:
            raise ValueError(
                "SUPABASE_KEY não fornecida. "
                "Configure via parâmetro ou variável de ambiente."
            )
        
        self.client: Client = create_client(
            self.supabase_url,
            self.supabase_key
        )
    
    def _extrair_campos_vaga(
        self,
        analise_json: Dict[str, Any],
        texto_vaga: str
    ) -> Dict[str, Any]:
        """
        Extrai e mapeia campos da análise para a tabela vagas_analisadas.
        """
        titulo_vaga = analise_json.get("titulo_vaga", "")
        empresa = analise_json.get("empresa", "")
        localizacao = analise_json.get("localizacao", "")
        modalidade = analise_json.get("modalidade", "")
        tipo_vaga = analise_json.get("tipo_vaga", "")
        match_score = analise_json.get("match_score", 0)
        classificacao = analise_json.get("classificacao", "descartar")
        resumo_personalizado = analise_json.get("resumo_personalizado", "")
        
        motivos_match = analise_json.get("motivos_match", [])
        gaps = analise_json.get("gaps", [])
        
        if classificacao == "aplicar":
            should_apply = True
            needs_review = False
        elif classificacao == "revisar":
            should_apply = True
            needs_review = True
        else:
            should_apply = False
            needs_review = False
        
        vaga_data = {
            "titulo_vaga": titulo_vaga,
            "empresa": empresa,
            "localizacao": localizacao,
            "modalidade": modalidade,
            "tipo_vaga": tipo_vaga,
            "texto_bruto_vaga": texto_vaga,
            "match_score": int(match_score) if str(match_score).isdigit() else 0,
            "classificacao": classificacao,
            "should_apply": should_apply,
            "needs_review": needs_review,
            "motivos_match": motivos_match,
            "gaps": gaps,
            "resumo_personalizado": resumo_personalizado,
            "raw_response": analise_json,
            "status_fluxo": self._determinar_status_fluxo(classificacao),
            "url_vaga": analise_json.get("url_vaga", None),
            "fonte_vaga": analise_json.get("fonte_vaga", None),
        }
        
        return vaga_data
    
    def _determinar_status_fluxo(self, classificacao: str) -> str:
        if classificacao == "aplicar":
            return "aprovada_para_candidatura"
        elif classificacao == "revisar":
            return "revisao_manual"
        else:
            return "descartada"
    
    def _validar_campos_obrigatorios(
        self,
        vaga_data: Dict[str, Any]
    ) -> bool:
        campos_obrigatorios = [
            "titulo_vaga",
            "empresa",
            "texto_bruto_vaga",
            "match_score",
            "classificacao",
            "should_apply",
            "needs_review",
        ]
        
        for campo in campos_obrigatorios:
            if campo not in vaga_data or vaga_data[campo] is None:
                print(f"[x] Campo obrigatório ausente: {campo}")
                return False
        
        return True
    
    def salvar_vaga(
        self,
        analise_json: Dict[str, Any],
        texto_vaga: str
    ) -> bool:
        """
        Salva resultado da análise de vaga no Supabase.
        """
        try:
            vaga_data = self._extrair_campos_vaga(analise_json, texto_vaga)
            
            if not self._validar_campos_obrigatorios(vaga_data):
                print("[x] Validação de campos falhou")
                return False
            
            print("[*] Conectando ao Supabase...")
            response = self.client.table("vagas_analisadas").insert(
                vaga_data
            ).execute()
            
            if response.data:
                vaga_id = response.data[0].get("id") if response.data else None
                print(f"[✓] Vaga salva com sucesso no Supabase!")
                print(f"    ID: {vaga_id}")
                print(f"    Empresa: {vaga_data['empresa']}")
                print(f"    Score: {vaga_data['match_score']}")
                print(f"    Classificação: {vaga_data['classificacao']}")
                print(f"    Status: {vaga_data['status_fluxo']}")
                return True
            else:
                print("[x] Resposta vazia do Supabase")
                return False
        
        except Exception as e:
            print(f"[x] Erro ao salvar no Supabase: {str(e)}")
            print(f"    Tipo de erro: {type(e).__name__}")
            return False
    
    def salvar_vaga_com_arquivo(
        self,
        caminho_analise: str,
        caminho_vaga: str
    ) -> bool:
        try:
            if not Path(caminho_analise).exists():
                print(f"[x] Arquivo de análise não encontrado: {caminho_analise}")
                return False
            
            with open(caminho_analise, "r", encoding="utf-8") as f:
                analise_json = json.load(f)
            
            if not Path(caminho_vaga).exists():
                print(f"[x] Arquivo de vaga não encontrado: {caminho_vaga}")
                return False
            
            with open(caminho_vaga, "r", encoding="utf-8") as f:
                texto_vaga = f.read()
            
            return self.salvar_vaga(analise_json, texto_vaga)
        
        except json.JSONDecodeError as e:
            print(f"[x] Erro ao decodificar JSON: {e}")
            return False
        except IOError as e:
            print(f"[x] Erro ao ler arquivo: {e}")
            return False
        except Exception as e:
            print(f"[x] Erro inesperado: {e}")
            return False
    
    def listar_vagas_recentes(self, limite: int = 10) -> Optional[List[Dict]]:
        try:
            response = self.client.table("vagas_analisadas").select(
                "id, titulo_vaga, empresa, match_score, classificacao, created_at"
            ).order(
                "created_at",
                desc=True
            ).limit(limite).execute()
            
            return response.data
        except Exception as e:
            print(f"[x] Erro ao listar vagas: {e}")
            return None

    def listar_vagas_para_candidatura(
        self,
        limite: int = 20,
        incluir_revisao_manual: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        try:
            status_fluxo = ["aprovada_para_candidatura"]
            if incluir_revisao_manual:
                status_fluxo.append("revisao_manual")

            response = self.client.table("vagas_analisadas").select(
                "id, titulo_vaga, empresa, localizacao, modalidade, tipo_vaga, "
                "url_vaga, fonte_vaga, match_score, classificacao, should_apply, "
                "needs_review, resumo_personalizado, status_fluxo, created_at"
            ).in_(
                "status_fluxo",
                status_fluxo
            ).order(
                "match_score",
                desc=True
            ).limit(limite).execute()

            return response.data
        except Exception as e:
            print(f"[x] Erro ao listar vagas para candidatura: {e}")
            return None

    def buscar_candidatura_por_vaga(
        self,
        vaga_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("candidaturas").select(
                "id, vaga_id, status_candidatura, created_at"
            ).eq(
                "vaga_id",
                vaga_id
            ).limit(1).execute()

            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"[x] Erro ao buscar candidatura da vaga {vaga_id}: {e}")
            return None

    def criar_candidatura(
        self,
        vaga_id: str,
        status_candidatura: str = "pendente",
        mensagem_enviada: Optional[str] = None,
        curriculo_usado: Optional[str] = None,
        payload_candidatura: Optional[Dict[str, Any]] = None,
        retorno_site: Optional[str] = None,
        observacoes: Optional[str] = None,
        data_envio: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            candidatura_data = {
                "vaga_id": vaga_id,
                "status_candidatura": status_candidatura,
                "mensagem_enviada": mensagem_enviada,
                "curriculo_usado": curriculo_usado,
                "payload_candidatura": payload_candidatura or {},
                "retorno_site": retorno_site,
                "observacoes": observacoes,
                "data_envio": data_envio,
            }

            response = self.client.table("candidaturas").insert(
                candidatura_data
            ).execute()

            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"[x] Erro ao criar candidatura: {e}")
            return None

    def atualizar_status_vaga(
        self,
        vaga_id: str,
        status_fluxo: str
    ) -> bool:
        try:
            response = self.client.table("vagas_analisadas").update(
                {"status_fluxo": status_fluxo}
            ).eq(
                "id",
                vaga_id
            ).execute()

            return bool(response.data)
        except Exception as e:
            print(f"[x] Erro ao atualizar status da vaga {vaga_id}: {e}")
            return False

    def atualizar_candidatura(
        self,
        candidatura_id: str,
        dados_atualizacao: Dict[str, Any]
    ) -> bool:
        try:
            response = self.client.table("candidaturas").update(
                dados_atualizacao
            ).eq(
                "id",
                candidatura_id
            ).execute()

            return bool(response.data)
        except Exception as e:
            print(f"[x] Erro ao atualizar candidatura {candidatura_id}: {e}")
            return False


def main():
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pbmhrmucjfqgrrovbmjn.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_r_xrCK7kvZGZ2CXZXlWSyw_PxbmjS3W")
    
    if SUPABASE_URL == "COLOCAR_AQUI" or SUPABASE_KEY == "COLOCAR_AQUI":
        print("[!] Configure SUPABASE_URL e SUPABASE_KEY antes de executar")
        print("    Você pode usar variáveis de ambiente ou parâmetros")
        return False
    
    try:
        client = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)
        print("[✓] Cliente Supabase inicializado com sucesso")
        
        vagas = client.listar_vagas_recentes(limite=5)
        if vagas is not None:
            print(f"[✓] Conexão funcionando! {len(vagas)} vagas no banco")
        
        return True
    
    except Exception as e:
        print(f"[x] Erro ao inicializar cliente: {e}")
        return False


if __name__ == "__main__":
    main()
