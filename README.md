# 🤖 Projeto AgentAI — Automação Inteligente de Busca, Análise e Candidatura em Vagas

Projeto desenvolvido com foco em automatizar o fluxo de candidatura para vagas de tecnologia, principalmente no LinkedIn, passando por etapas de **coleta**, **extração**, **normalização**, **análise com IA**, **persistência em banco de dados** e **execução de candidatura automática** quando houver match com o perfil do candidato.

## 👨‍💻 Desenvolvedor

- Gabriel Labarca Del Bianco

---

## 🧠 Visão Geral

A ideia central do projeto é construir um pipeline capaz de:

1. Buscar vagas automaticamente no LinkedIn
2. Extrair os principais dados de cada vaga
3. Estruturar essas informações em JSON
4. Analisar o quanto a vaga combina com o perfil do candidato
5. Salvar tudo no Supabase
6. Decidir se a vaga deve ser descartada, revisada ou aplicada
7. Executar a candidatura automática no LinkedIn Easy Apply quando aplicável

O sistema foi organizado por responsabilidades, evitando misturar:

- coleta de dados
- análise com IA
- banco de dados
- candidatura automática
- orquestração do fluxo

---

## 🏗️ Arquitetura do Projeto

O projeto está dividido em 5 grandes camadas:

### 1. Coleta de vagas

Responsável por:

- buscar links no LinkedIn
- abrir páginas de vaga
- extrair os dados visíveis
- normalizar os campos

### 2. Análise de aderência

Responsável por:

- montar o prompt com perfil + preferências + vaga
- enviar ao Ollama
- extrair o JSON final
- classificar a vaga

### 3. Persistência

Responsável por:

- salvar vagas analisadas no Supabase
- controlar o status do fluxo
- armazenar candidaturas

### 4. Candidatura automática

Responsável por:

- abrir a vaga no LinkedIn
- detectar Easy Apply
- preencher etapas do formulário
- tentar enviar a candidatura

### 5. Orquestração

Responsável por:

- expor endpoints FastAPI
- permitir integração com n8n
- organizar o fluxo de ponta a ponta

---

## 🛠️ Etapas do Desenvolvimento

### 🗄️ Banco de Dados com Supabase

O projeto utiliza o [Supabase](https://supabase.com/) como banco de dados principal.
Ele foi escolhido por facilitar o uso de PostgreSQL gerenciado em nuvem, sem necessidade de hospedar o banco manualmente.

As tabelas principais são:

- `vagas_analisadas`
- `candidaturas`

#### 📌 Tabela `vagas_analisadas`

Armazena:

- dados extraídos da vaga
- texto bruto da vaga
- score de aderência
- classificação
- decisão do fluxo
- resposta estruturada da análise
- `url_vaga`
- `fonte_vaga`

#### 📌 Tabela `candidaturas`

Armazena:

- referência da vaga
- status da candidatura
- retorno do executor
- observações
- payload usado na execução

Essa estrutura permite acompanhar todo o ciclo:

- vaga encontrada
- vaga analisada
- vaga aprovada
- candidatura executada ou pendente

---

### ⚙️ Back-end com FastAPI

O projeto possui uma API em **FastAPI** para centralizar a comunicação entre:

- n8n
- scripts Python
- Ollama
- Supabase

#### Endpoints principais

- `GET /`
- `POST /analisar`
- `POST /coletar`
- `POST /candidatar`

#### 📌 `GET /`

Endpoint simples para verificar se a API está ativa.

Exemplo de resposta:

```json
{
  "status": "ok",
  "mensagem": "API rodando"
}
```

#### 📌 `POST /analisar`

Recebe uma vaga já estruturada e dispara a análise com IA.

Exemplo de payload:

```json
{
  "vaga": "Texto bruto da vaga...",
  "url_vaga": "https://www.linkedin.com/jobs/view/123456789/",
  "fonte_vaga": "LinkedIn"
}
```

#### 📌 `POST /coletar`

Executa a camada de coleta de vagas do LinkedIn.

#### 📌 `POST /candidatar`

Executa a fila de candidaturas aprovadas, consultando o Supabase e, se aplicável, usando o executor do LinkedIn Easy Apply.

---

### 🧾 Camada de Análise com Ollama

A análise é responsável por transformar o texto bruto da vaga em uma decisão objetiva para o fluxo.

Essa camada usa:

- perfil do candidato
- preferências profissionais
- prompt-base
- Ollama local

#### 📌 Fluxo da análise

1. Carregar o prompt
2. Carregar o perfil do candidato
3. Carregar as preferências
4. Montar o prompt final
5. Enviar ao Ollama
6. Extrair o JSON da resposta
7. Salvar a análise em arquivo
8. Integrar com o Supabase

#### 📌 Resultado esperado

O JSON final contém campos como:

- `titulo_vaga`
- `empresa`
- `localizacao`
- `modalidade`
- `tipo_vaga`
- `match_score`
- `classificacao`
- `should_apply`
- `motivos_match`
- `gaps`
- `resumo_personalizado`
- `url_vaga`
- `fonte_vaga`

#### 📌 Classificação da vaga

A análise pode gerar:

- `aplicar`
- `revisar`
- `descartar`

Essas classificações alimentam o campo `status_fluxo` no banco:

- `aprovada_para_candidatura`
- `revisao_manual`
- `descartada`

---

### 🔎 Coleta de Vagas no LinkedIn

A coleta foi separada em uma pasta própria para não misturar com análise nem candidatura.

Estrutura da camada:

```
scripts/coleta_dados/buscar_vagas_linkedin.py
scripts/coleta_dados/extrair_dados_vaga.py
scripts/coleta_dados/normalizar_vaga.py
scripts/coleta_dados/coletar_vagas_pipeline.py
```

#### 📌 1. Busca de URLs

O módulo `buscar_vagas_linkedin.py` é responsável por:

- abrir a listagem de vagas do LinkedIn
- coletar links únicos de vagas
- aplicar filtros como cargo e localização
- permitir filtro de Easy Apply
- detectar bloqueios, login e checkpoint

Exemplo de filtros usados:

- `cargo`
- `localizacao`
- `modalidade`
- `candidatura_simplificada`

#### 📌 2. Extração dos dados da vaga

O módulo `extrair_dados_vaga.py` é responsável por:

- abrir cada vaga individualmente
- extrair os campos principais visíveis
- detectar erro de login/bloqueio
- devolver estrutura com status

Campos mínimos extraídos:

- `url_vaga`
- `titulo_vaga`
- `empresa`
- `localizacao`
- `texto_vaga`

Campos adicionais quando possível:

- `modalidade`
- `tipo_vaga`

#### 📌 3. Normalização

O módulo `normalizar_vaga.py` recebe a extração bruta e padroniza o formato final.

Formato de saída:

```json
{
  "status": "ok",
  "url_vaga": "",
  "titulo_vaga": "",
  "empresa": "",
  "localizacao": "",
  "modalidade": "",
  "tipo_vaga": "",
  "texto_vaga": "",
  "fonte_vaga": "LinkedIn",
  "mensagem": ""
}
```

#### 📌 4. Pipeline de coleta

O orquestrador `coletar_vagas_pipeline.py` executa a cadeia completa:

1. buscar vagas
2. iterar links encontrados
3. extrair dados brutos
4. normalizar os dados
5. devolver a lista final pronta para análise

---

### 💼 Candidatura Automática com Playwright

A candidatura automática foi construída para vagas que usam LinkedIn Easy Apply.

O executor principal está em:

```
scripts/candidatura/linkedin_easy_apply_executor.py
```

Ele é chamado pelo fluxo de candidatura quando:

- a vaga está aprovada
- a fonte é LinkedIn
- existe `url_vaga`
- a vaga está elegível para candidatura

#### 📌 O que o executor faz

1. abre a vaga
2. detecta o botão Easy Apply
3. abre o modal de candidatura
4. lê os campos por etapa
5. tenta preencher campos conhecidos
6. faz scroll no modal
7. tenta clicar em **Avançar**, **Revisar** e **Enviar candidatura**

#### 📌 Estratégia usada

O sistema tenta ser conservador:

- se o campo for conhecido, preenche
- se já estiver preenchido, pula
- se for obrigatório e desconhecido, sinaliza revisão manual

Essa decisão foi importante para evitar respostas erradas em formulários variáveis.

---

### 🔄 Execução da Fila de Candidaturas

O script `scripts/candidatura/executar_candidaturas.py` é responsável por:

- consultar o Supabase
- buscar vagas elegíveis
- verificar se já existe candidatura para a vaga
- escolher o executor certo
- registrar o resultado em `candidaturas`

Esse fluxo separa bem:

- análise
- decisão
- execução

---

### 🤝 Orquestração com n8n

O projeto também foi estruturado para ser integrado com n8n.

Exemplo de fluxo no n8n:

1. disparar coleta
2. transformar a lista em itens
3. analisar cada vaga
4. verificar se `classificacao == aplicar`
5. chamar a etapa de candidatura

O n8n ajuda principalmente em:

- automação de ponta a ponta
- repetição de fluxos
- integração entre serviços
- monitoramento de execuções

---

## 📂 Estrutura do Projeto

```bash
Projeto_AgentAI/
├── api.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
├── browser_profiles/
├── data/
│   ├── perfil.json
│   ├── preferencias.json
│   └── vagas/
├── database/
│   └── schema.sql
├── outputs/
├── prompts/
│   └── avaliador_vagas.txt
├── scripts/
│   ├── analise/
│   │   └── analisar_vaga.py
│   ├── candidatura/
│   │   ├── executar_candidaturas.py
│   │   └── linkedin_easy_apply_executor.py
│   ├── coleta_dados/
│   │   ├── buscar_vagas_linkedin.py
│   │   ├── extrair_dados_vaga.py
│   │   ├── normalizar_vaga.py
│   │   └── coletar_vagas_pipeline.py
│   ├── compartilhado/
│   │   └── supabase_client.py
│   └── testes/
│       ├── teste_1_abrir_navegador.py
│       ├── teste_local.py
│       └── testar_linkedin_executor.py
└── n8n/
```

---

## 🧪 Estratégia de Testes

Ao longo do desenvolvimento, o projeto foi validado com:

- testes locais da análise com vaga fixa
- testes do endpoint `/analisar`
- testes de integração com Supabase
- testes de coleta de links
- testes de extração de vaga individual
- testes do fluxo Easy Apply
- testes do workflow no n8n

Também foram adicionados logs para debugging em pontos críticos como:

- origem do título extraído
- origem da empresa
- origem da localização
- detecção de login/bloqueio
- progresso das etapas do Easy Apply

---

## 🧠 Aprendizados

Este projeto foi uma excelente oportunidade para praticar:

- arquitetura modular em Python
- integração com LLM local usando Ollama
- APIs com FastAPI
- persistência com Supabase
- scraping e automação com Playwright
- normalização de dados
- orquestração com n8n
- debugging de fluxos híbridos entre Docker, navegador e API
- tratamento de erros em sistemas automatizados reais

---

## 🚀 Como Executar

### Requisitos

- Python 3.12+
- Git
- Docker Desktop
- Supabase configurado
- Ollama instalado localmente
- modelo do Ollama baixado
- Playwright instalado localmente para automação visual

### 1. Clonar o repositório

```bash
git clone <URL_DO_REPOSITORIO>
cd Projeto_AgentAI
```

### 2. Criar e ativar o ambiente virtual

No Git Bash:

```bash
python -m venv venv
source venv/Scripts/activate
```

No PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar dependências locais

Para rodar a automação local completa com Playwright:

```bash
pip install fastapi uvicorn python-dotenv requests supabase playwright
playwright install
```

### 4. Configurar o `.env`

Exemplo:

```env
SUPABASE_URL=...
SUPABASE_KEY=...
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
TZ=America/Sao_Paulo
N8N_PORT=5678
LINKEDIN_EMAIL=...
LINKEDIN_COUNTRY_CODE=Brasil (+55)
LINKEDIN_PHONE=...
LINKEDIN_GRADUATION_DATE=122027
LINKEDIN_SALARY_EXPECTATION=1700
LINKEDIN_WORKED_AT_COMPANY_GROUP=No
LINKEDIN_FOLLOW_COMPANY=false
LINKEDIN_RESUME_PATH=assets/seu_curriculo.pdf
```

### 5. Rodar o Ollama

Se o Ollama não estiver ativo em background:

```bash
ollama serve
```

Para testar:

```bash
curl http://127.0.0.1:11434/api/tags
```

### 6. Subir a infraestrutura com Docker

O projeto pode usar Docker para facilitar o ambiente local, principalmente para n8n e FastAPI:

```bash
docker compose up --build -d
```

Acesso:

- n8n: http://localhost:5678
- FastAPI: http://localhost:8000
- Swagger: http://localhost:8000/docs

### 7. Rodar análise local

```bash
py scripts/analise/analisar_vaga.py --vaga-file data/vagas/exemplo_onerpm.txt
```

Ou:

```bash
py scripts/testes/teste_local.py --vaga-file data/vagas/exemplo_onerpm.txt
```

### 8. Rodar coleta local

```bash
py scripts/coleta_dados/coletar_vagas_pipeline.py --cargo "estagio ti" --localizacao "Sao Paulo, SP"
```

### 9. Testar navegador com Playwright

```bash
py scripts/testes/teste_1_abrir_navegador.py
```

### 10. Testar candidatura automática

```bash
py scripts/testes/testar_linkedin_executor.py
```

Ou executar a fila:

```bash
py scripts/candidatura/executar_candidaturas.py
```

---

## 📌 Observações Importantes

- A análise com IA depende do Ollama ativo.
- A automação visual com LinkedIn funciona melhor localmente, fora do container.
- O perfil persistido do navegador é essencial para evitar login repetido.
- Vagas Easy Apply são tratadas de forma diferente das vagas comuns.
- O projeto foi pensado para separar claramente análise, coleta e candidatura.

---

## 🔮 Próximos Passos

Algumas melhorias futuras possíveis:

- validação mais forte do JSON do LLM
- melhoria dos fallbacks de extração
- dashboard para acompanhamento de candidaturas
- API local separada só para Playwright
- expansão para outras fontes de vaga além do LinkedIn
- métricas e logs mais detalhados
- fila mais inteligente para retries e revisão manual

---

## 📄 Licença

Este projeto foi desenvolvido com fins educacionais, experimentais e de estudo em:

- automação de processos
- IA aplicada
- análise de vagas
- integração entre sistemas
- automação de candidatura
