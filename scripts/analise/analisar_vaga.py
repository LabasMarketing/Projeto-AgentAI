#!/usr/bin/env python3
"""
Script de teste local para análise de vagas com Ollama.
Lê perfil, preferências e vaga, envia ao Ollama, salva resultado e integra com Supabase.
Aceita vaga dinâmica via argumento, arquivo ou stdin, mantendo fallback para o exemplo local.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv
load_dotenv()

try:
    from scripts.compartilhado.supabase_client import SupabaseClient
    SUPABASE_DISPONIVEL = True
except ImportError:
    try:
        from scripts.compartilhado.supabase_client import SupabaseClient
        SUPABASE_DISPONIVEL = True
    except ImportError as e:
        print(f"[!] Erro ao importar SupabaseClient: {e}")
        SUPABASE_DISPONIVEL = False


class AnalisadorVagas:
    """Classe para análise de vagas usando Ollama."""
    
    def __init__(
        self,
        ollama_host: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.ollama_host = (
            ollama_host
            or os.getenv("OLLAMA_HOST")
            or os.getenv("OLLAMA_URL")
            or "http://localhost:11434"
        )
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.project_root = Path(__file__).resolve().parents[2]
        self.caminho_vaga_padrao = "data/vagas/exemplo_onerpm.txt"
        
    def carregar_arquivo(self, caminho_relativo: str) -> str:
        caminho_completo = self.project_root / caminho_relativo
        if not caminho_completo.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_completo}")
        
        with open(caminho_completo, "r", encoding="utf-8") as f:
            return f.read()
    
    def carregar_json(self, caminho_relativo: str) -> Dict[str, Any]:
        conteudo = self.carregar_arquivo(caminho_relativo)
        return json.loads(conteudo)
    
    def formatar_perfil(self, perfil: Dict[str, Any]) -> str:
        linhas = []
        
        linhas.append("PERFIL PROFISSIONAL:")
        linhas.append(f"Nome: {perfil['informacoes_pessoais']['nome']}")
        linhas.append(f"Objetivo: {perfil['informacoes_pessoais']['objetivo']}")
        linhas.append("")
        
        linhas.append("FORMAÇÃO:")
        linhas.append(f"Curso: {perfil['formacao']['curso']}")
        linhas.append(f"Instituição: {perfil['formacao']['instituicao']}")
        linhas.append(f"Período: {perfil['formacao']['periodo']}")
        linhas.append("")
        
        linhas.append("STACK TECNOLÓGICO:")
        stack = perfil['stack_principal']
        linhas.append(f"Linguagens: {', '.join(stack['linguagens'])}")
        linhas.append(f"Frameworks Backend: {', '.join(stack['frameworks_backend'])}")
        linhas.append(f"Frameworks Frontend: {', '.join(stack['frameworks_frontend'])}")
        linhas.append(f"Bancos de Dados: {', '.join(stack['bancos_dados'])}")
        linhas.append(f"Cloud: {', '.join(stack['cloud'])}")
        linhas.append(f"DevOps: {', '.join(stack['devops'])}")
        linhas.append("")
        
        linhas.append("PROJETOS:")
        for projeto in perfil['projetos']:
            linhas.append(f"- {projeto['nome']}: {projeto['descricao']}")
            linhas.append(f"  Stack: {', '.join(projeto['stack'])}")
        linhas.append("")
        
        linhas.append("CERTIFICAÇÕES:")
        for cert in perfil['certificacoes']:
            linhas.append(f"- {cert}")
        linhas.append("")
        
        linhas.append("FORÇAS:")
        for forca in perfil['forcas']:
            linhas.append(f"- {forca}")
        
        return "\n".join(linhas)
    
    def formatar_preferencias(self, preferencias: Dict[str, Any]) -> str:
        linhas = []
        
        linhas.append("PREFERÊNCIAS DO CANDIDATO:")
        linhas.append("")
        
        linhas.append("CARGOS DESEJADOS:")
        for cargo in preferencias['cargo_desejado']:
            linhas.append(f"- {cargo}")
        linhas.append("")
        
        linhas.append("MODALIDADE DE TRABALHO:")
        for mod in preferencias['modalidade']:
            linhas.append(f"- {mod}")
        linhas.append("")
        
        linhas.append("LOCALIZAÇÃO:")
        for loc in preferencias['localizacao']:
            linhas.append(f"- {loc}")
        linhas.append("")
        
        linhas.append("TIPO DE CONTRATO:")
        for tipo in preferencias['tipo_contrato']:
            linhas.append(f"- {tipo}")
        linhas.append("")
        
        linhas.append("DISPONIBILIDADE:")
        for disp in preferencias['disponibilidade']:
            linhas.append(f"- {disp}")
        linhas.append("")
        
        linhas.append("PRIORIDADES:")
        for prio in preferencias['prioridades']:
            linhas.append(f"- {prio}")
        linhas.append("")
        
        linhas.append("ACEITÁVEL:")
        for ace in preferencias['aceitavel']:
            linhas.append(f"- {ace}")
        linhas.append("")
        
        linhas.append("EVITAR:")
        for eva in preferencias['evitar']:
            linhas.append(f"- {eva}")
        
        return "\n".join(linhas)
    
    def montar_prompt(
        self,
        template_prompt: str,
        perfil: str,
        preferencias: str,
        vaga: str
    ) -> str:
        prompt = template_prompt
        prompt = prompt.replace("{{PERFIL}}", perfil)
        prompt = prompt.replace("{{PREFERENCIAS}}", preferencias)
        prompt = prompt.replace("{{VAGA}}", vaga)
        return prompt
    
    def enviar_para_ollama(self, prompt: str) -> str:
        host_normalizado = self.ollama_host.rstrip("/")
        if host_normalizado.endswith("/api/generate"):
            url = host_normalizado
        else:
            url = f"{host_normalizado}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.3
        }
        
        try:
            print(f"[*] Enviando requisição para {url}...")
            response = requests.post(url, json=payload, timeout=600)
            response.raise_for_status()
            
            data = response.json()
            return data.get("response", "")
        
        except requests.exceptions.ConnectionError:
            raise requests.RequestException(
                f"Erro: Não consegui conectar ao Ollama em {self.ollama_host}. "
                "Verifique se Ollama está rodando."
            )
        except requests.exceptions.Timeout:
            raise requests.RequestException(
                "Erro: Timeout na comunicação com Ollama. "
                "A requisição demorou muito."
            )
    
    def extrair_json(self, resposta: str) -> Dict[str, Any]:
        resposta = resposta.strip()
        inicio = resposta.find('{')
        fim = resposta.rfind('}')
        
        if inicio == -1 or fim == -1 or inicio >= fim:
            raise ValueError(
                f"Não consegui encontrar JSON válido na resposta:\n{resposta[:200]}"
            )
        
        json_str = resposta[inicio:fim+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido extraído: {e}\n{json_str[:200]}")
    
    def salvar_resultado(self, resultado: Dict[str, Any], caminho_saida: str) -> None:
        caminho_completo = self.project_root / caminho_saida
        caminho_completo.parent.mkdir(parents=True, exist_ok=True)
        
        with open(caminho_completo, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        
        print(f"[✓] Resultado salvo em: {caminho_completo}")
    
    def obter_vaga_entrada(
        self,
        vaga_texto: Optional[str] = None,
        vaga_arquivo: Optional[str] = None
    ) -> Tuple[str, str]:
        if vaga_texto and vaga_texto.strip():
            return vaga_texto.strip(), "argumento"

        if vaga_arquivo:
            caminho = Path(vaga_arquivo)
            if not caminho.is_absolute():
                caminho = self.project_root / vaga_arquivo

            if not caminho.exists():
                raise FileNotFoundError(f"Arquivo da vaga não encontrado: {caminho}")

            with open(caminho, "r", encoding="utf-8") as arquivo:
                return arquivo.read(), f"arquivo:{caminho}"

        return self.carregar_arquivo(self.caminho_vaga_padrao), "fallback_exemplo"

    def _salvar_no_supabase(
        self,
        resultado: Dict[str, Any],
        vaga_texto: str
    ) -> None:
        if not SUPABASE_DISPONIVEL:
            print("[!] Biblioteca 'supabase' não instalada. Pulando integração com banco.")
            print("    Execute: pip install supabase")
            return
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("[!] Variáveis SUPABASE_URL ou SUPABASE_KEY não configuradas.")
            print("    Pulando integração com banco.")
            return
        
        try:
            print("[*] Conectando ao Supabase...")
            supabase_client = SupabaseClient(supabase_url, supabase_key)
            sucesso = supabase_client.salvar_vaga(resultado, vaga_texto)
            
            if sucesso:
                print("[✓] Integração com Supabase concluída com sucesso!")
            else:
                print("[✗] Falha na integração com Supabase")
        
        except Exception as e:
            print(f"[✗] Erro ao integrar com Supabase: {e}")
    
    def analisar_vaga(
        self,
        vaga_texto: Optional[str] = None,
        vaga_arquivo: Optional[str] = None,
        url_vaga: Optional[str] = None,
        fonte_vaga: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            print("\n" + "="*60)
            print("ANÁLISE DE VAGA - AGENTE IA")
            print("="*60 + "\n")
            
            print("[1/6] Carregando arquivo de prompt...")
            template_prompt = self.carregar_arquivo("prompts/avaliador_vagas.txt")
            
            print("[2/6] Carregando perfil do candidato...")
            perfil_dict = self.carregar_json("data/perfil.json")
            
            print("[3/6] Carregando preferências...")
            preferencias_dict = self.carregar_json("data/preferencias.json")
            
            print("[4/6] Carregando descrição da vaga...")
            vaga, origem_vaga = self.obter_vaga_entrada(vaga_texto, vaga_arquivo)
            print(f"    Origem da vaga: {origem_vaga}")
            
            print("[5/6] Montando prompt com dados...")
            perfil_formatado = self.formatar_perfil(perfil_dict)
            preferencias_formatada = self.formatar_preferencias(preferencias_dict)
            prompt_final = self.montar_prompt(
                template_prompt,
                perfil_formatado,
                preferencias_formatada,
                vaga
            )
            
            print("[6/6] Enviando para análise no Ollama...")
            resposta_ollama = self.enviar_para_ollama(prompt_final)
            
            print("\n[*] Extraindo JSON da resposta...")
            resultado = self.extrair_json(resposta_ollama)

            if url_vaga:
                resultado["url_vaga"] = url_vaga
            if fonte_vaga:
                resultado["fonte_vaga"] = fonte_vaga
            
            print("[*] Salvando resultado...")
            self.salvar_resultado(resultado, "outputs/analise_teste.json")
            
            print("[*] Integrando com Supabase...")
            self._salvar_no_supabase(resultado, vaga)
            
            print("\n" + "="*60)
            print("RESULTADO DA ANÁLISE")
            print("="*60)
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
            print("="*60 + "\n")
            
            return resultado
        
        except FileNotFoundError as e:
            print(f"\n[✗] Erro: {e}")
            return None
        except requests.RequestException as e:
            print(f"\n[✗] Erro de conexão: {e}")
            return None
        except ValueError as e:
            print(f"\n[✗] Erro ao processar resposta: {e}")
            return None
        except Exception as e:
            print(f"\n[✗] Erro inesperado: {e}")
            return None


def criar_parser_argumentos() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analisa uma vaga usando perfil local + Ollama + Supabase."
    )
    parser.add_argument(
        "vaga",
        nargs="?",
        help="Texto bruto da vaga enviado diretamente pela linha de comando."
    )
    parser.add_argument(
        "--vaga-file",
        dest="vaga_file",
        help="Arquivo com a descrição da vaga."
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Lê o texto da vaga da entrada padrão."
    )
    return parser


def resolver_vaga_argumentos(args: argparse.Namespace) -> Tuple[Optional[str], Optional[str]]:
    if args.stdin:
        conteudo = sys.stdin.read().strip()
        if not conteudo:
            raise ValueError("Nenhum conteúdo recebido via stdin.")
        return conteudo, None

    if args.vaga:
        return args.vaga, None

    if args.vaga_file:
        return None, args.vaga_file

    return None, None


def main():
    parser = criar_parser_argumentos()
    args = parser.parse_args()

    ollama_host = os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_URL") or "http://localhost:11434"
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    
    analisador = AnalisadorVagas(
        ollama_host=ollama_host,
        model=ollama_model
    )
    
    try:
        vaga_texto, vaga_arquivo = resolver_vaga_argumentos(args)
    except ValueError as e:
        print(f"\n[x] Erro de entrada: {e}")
        return 1

    resultado = analisador.analisar_vaga(
        vaga_texto=vaga_texto,
        vaga_arquivo=vaga_arquivo
    )
    
    return 0 if resultado else 1


if __name__ == "__main__":
    sys.exit(main())
