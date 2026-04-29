#!/usr/bin/env python3
"""
Exemplo de uso direto do cliente Supabase para salvar vagas.
Útil para testes ou integração direta sem executar análise do Ollama.
"""

import json
import os
from pathlib import Path

# Adicionar scripts ao path
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in __import__('sys').path:
    __import__('sys').path.insert(0, str(scripts_dir))

from scripts.compartilhado.supabase_client import SupabaseClient


def exemplo_1_salvar_diretamente():
    """
    Exemplo 1: Salvar análise já pronta direto para o banco.
    Não precisa de Ollama ou Arquivo.
    """
    print("\n" + "="*60)
    print("EXEMPLO 1: Salvar Análise Diretamente")
    print("="*60 + "\n")
    
    # Configurar credenciais
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("[!] Configure SUPABASE_URL e SUPABASE_KEY")
        return False
    
    # Criar cliente
    try:
        client = SupabaseClient(supabase_url, supabase_key)
        print("[✓] Cliente Supabase conectado")
    except Exception as e:
        print(f"[✗] Erro ao conectar: {e}")
        return False
    
    # Preparar dados (simulando resposta do Ollama)
    analise_json = {
        "titulo_vaga": "Senior Backend Developer",
        "empresa": "Tech Startup XYZ",
        "localizacao": "São Paulo, SP",
        "modalidade": "Remoto",
        "tipo_vaga": "CLT",
        "match_score": 85,
        "classificacao": "aplicar",
        "should_apply": True,
        "needs_review": False,
        "motivos_match": [
            "Stack em Python/FastAPI",
            "Remoto (preferência do candidato)",
            "Salário competitivo",
            "Empresa em crescimento"
        ],
        "gaps": [
            "Requer AWS (candidato tem GCP)"
        ],
        "resumo_personalizado": "Excelente match! Vaga alinhada com sua stack e preferências. Recomenda-se aplicar.",
        "url_vaga": "https://example.com/vaga-123",
        "fonte_vaga": "LinkedIn"
    }
    
    texto_vaga = """
    Procuramos um Senior Backend Developer com expertise em Python.
    - Requisitos: 5+ anos com Python, FastAPI, PostgreSQL
    - Stack: Python, FastAPI, PostgreSQL, Docker, AWS
    - Modalidade: Remoto
    - Salário: R$ 15.000 - R$ 20.000
    - Benefícios: VR, VA, Saúde, Dental, Auxílio Educação
    """
    
    # Salvar no Supabase
    print("\n[*] Salvando vaga no Supabase...")
    sucesso = client.salvar_vaga(analise_json, texto_vaga)
    
    return sucesso


def exemplo_2_salvar_de_arquivo():
    """
    Exemplo 2: Salvar a partir dos arquivos gerados por teste_local.py
    """
    print("\n" + "="*60)
    print("EXEMPLO 2: Salvar de Arquivo (após teste_local.py)")
    print("="*60 + "\n")
    
    # Configurar credenciais
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("[!] Configure SUPABASE_URL e SUPABASE_KEY")
        return False
    
    # Criar cliente
    try:
        client = SupabaseClient(supabase_url, supabase_key)
        print("[✓] Cliente Supabase conectado")
    except Exception as e:
        print(f"[✗] Erro ao conectar: {e}")
        return False
    
    # Caminhos relativos à raiz do projeto
    project_root = Path(__file__).parent.parent
    caminho_analise = project_root / "outputs" / "analise_teste.json"
    caminho_vaga = project_root / "data" / "vagas" / "exemplo_onerpm.txt"
    
    print(f"\n[*] Buscando análise em: {caminho_analise}")
    print(f"[*] Buscando vaga em: {caminho_vaga}")
    
    if not caminho_analise.exists():
        print(f"[✗] Arquivo de análise não encontrado!")
        print(f"    Dica: Execute 'python scripts/teste_local.py' primeiro")
        return False
    
    if not caminho_vaga.exists():
        print(f"[✗] Arquivo de vaga não encontrado!")
        return False
    
    # Salvar usando arquivo
    print("\n[*] Salvando vaga no Supabase...")
    sucesso = client.salvar_vaga_com_arquivo(
        str(caminho_analise),
        str(caminho_vaga)
    )
    
    return sucesso


def exemplo_3_listar_vagas():
    """
    Exemplo 3: Listar vagas salvas no banco
    """
    print("\n" + "="*60)
    print("EXEMPLO 3: Listar Vagas Recentes")
    print("="*60 + "\n")
    
    # Configurar credenciais
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("[!] Configure SUPABASE_URL e SUPABASE_KEY")
        return False
    
    # Criar cliente
    try:
        client = SupabaseClient(supabase_url, supabase_key)
        print("[✓] Cliente Supabase conectado")
    except Exception as e:
        print(f"[✗] Erro ao conectar: {e}")
        return False
    
    # Listar vagas
    print("\n[*] Buscando 10 vagas mais recentes...")
    vagas = client.listar_vagas_recentes(limite=10)
    
    if vagas is None:
        print("[✗] Erro ao listar vagas")
        return False
    
    if not vagas:
        print("[!] Nenhuma vaga encontrada no banco")
        return True
    
    print(f"\n[✓] {len(vagas)} vagas encontradas:\n")
    
    for i, vaga in enumerate(vagas, 1):
        print(f"{i}. {vaga['titulo_vaga']} - {vaga['empresa']}")
        print(f"   Score: {vaga['match_score']} | Classificação: {vaga['classificacao']}")
        print(f"   Data: {vaga['created_at']}")
        print(f"   ID: {vaga['id']}\n")
    
    return True


def main():
    """
    Menu principal para escolher qual exemplo executar.
    """
    print("\n" + "="*60)
    print("EXEMPLOS DE USO - Cliente Supabase")
    print("="*60)
    
    print("\nEscolha uma opção:")
    print("1. Salvar análise diretamente (sem Ollama)")
    print("2. Salvar de arquivo (após teste_local.py)")
    print("3. Listar vagas recentes")
    print("4. Executar todos")
    print("0. Sair")
    
    # Verificar se em modo não-interativo
    import sys
    if not sys.stdin.isatty():
        # Executar modo não-interativo (por exemplo, em CI/CD)
        print("\n[*] Executando em modo não-interativo (todos os exemplos)...")
        exemplo_1_salvar_diretamente()
        exemplo_2_salvar_de_arquivo()
        exemplo_3_listar_vagas()
        return
    
    try:
        opcao = input("\nDigite a opção (0-4): ").strip()
        
        if opcao == "1":
            exemplo_1_salvar_diretamente()
        elif opcao == "2":
            exemplo_2_salvar_de_arquivo()
        elif opcao == "3":
            exemplo_3_listar_vagas()
        elif opcao == "4":
            exemplo_1_salvar_diretamente()
            exemplo_2_salvar_de_arquivo()
            exemplo_3_listar_vagas()
        elif opcao == "0":
            print("\nAté logo!")
        else:
            print("\n[✗] Opção inválida!")
    
    except KeyboardInterrupt:
        print("\n\n[!] Cancelado pelo usuário")
    except Exception as e:
        print(f"\n[✗] Erro inesperado: {e}")


if __name__ == "__main__":
    main()
