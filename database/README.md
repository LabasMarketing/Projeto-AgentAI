# Database - Agent IA

## 📋 Objetivo

Esta pasta contém toda a estrutura de persistência de dados do projeto Agent IA. Aqui estão definidas as tabelas do Supabase que armazenam:

1. **Vagas analisadas** - Resultados da análise de aderência feita pelo agente IA
2. **Candidaturas** - Registros de candidaturas geradas ou executadas pelo sistema

## 📁 Estrutura

```
database/
├── schema.sql          # Script SQL pronto para Supabase
├── README.md           # Este arquivo
```

## 📊 Tabelas Principais

### 1. `vagas_analisadas`

Armazena o resultado da análise de uma vaga de emprego feita pelo agente IA.

**Campos:**
- `id` (UUID) - Identificador único
- `titulo_vaga` (text) - Título da posição
- `empresa` (text) - Nome da empresa
- `localizacao` (text) - Localização da vaga
- `modalidade` (text) - Tipo de modalidade (presencial, remoto, híbrido)
- `tipo_vaga` (text) - Tipo de contrato (estágio, PJ, CLT, etc)
- `texto_bruto_vaga` (text) - Descrição completa e original da vaga
- `url_vaga` (text) - URL onde foi encontrada
- `fonte_vaga` (text) - Origem/fonte (LinkedIn, Gupy, etc)
- `match_score` (integer 0-100) - Nota de aderência calculada
- `classificacao` (text) - Recomendação: **aplicar**, **revisar** ou **descartar**
- `should_apply` (boolean) - Indica se deve aplicar automaticamente
- `needs_review` (boolean) - Indica se precisa de revisão manual
- `motivos_match` (JSONB) - Array com motivos que geram match
- `gaps` (JSONB) - Array com lacunas encontradas
- `resumo_personalizado` (text) - Análise resumida para o candidato
- `raw_response` (JSONB) - Resposta completa do agente IA para auditoria e debug
- `status_fluxo` (text) - Estado da vaga no sistema:
  - `analisada` - Acabou de ser analisada
  - `aprovada_para_candidatura` - Pronta para candidatura
  - `descartada` - Não recomendada
  - `revisao_manual` - Aguardando revisão humana
  - `candidatura_executada` - Candidatura já enviada
  - `erro` - Erro durante processamento
- `created_at` (timestamptz) - Quando foi analisada
- `updated_at` (timestamptz) - Última atualização

**Índices:**
- `match_score` - Para buscar vagas por score
- `classificacao` - Para filtrar por tipo de recomendação
- `status_fluxo` - Para acompanhamento de workflow
- `empresa` - Para histórico por empresa
- `created_at` - Para vagas mais recentes
- Índice composto em `status_fluxo + match_score`

---

### 2. `candidaturas`

Armazena registros de candidaturas geradas ou executadas pelo sistema para vagas aprovadas.

**Campos:**
- `id` (UUID) - Identificador único
- `vaga_id` (UUID, FK) - Referência à vaga em `vagas_analisadas`
- `status_candidatura` (text) - Estado da candidatura:
  - `pendente` - Criada, aguardando envio
  - `em_revisao` - Aguardando aprovação do usuário
  - `enviada` - Candidatura enviada com sucesso
  - `falhou` - Falha no envio
  - `cancelada` - Cancelada manualmente
- `mensagem_enviada` (text) - Mensagem ou descrição do candidato
- `curriculo_usado` (text) - Qual currículo foi utilizado
- `payload_candidatura` (JSONB) - Dados completos enviados (campos do formulário, etc)
- `retorno_site` (text) - Resposta ou feedback do site/plataforma
- `observacoes` (text) - Notas ou observações do sistema/usuário
- `data_envio` (timestamptz) - Quando foi enviada
- `created_at` (timestamptz) - Quando foi criada
- `updated_at` (timestamptz) - Última atualização

**Índices:**
- `vaga_id` - Para consultar candidaturas por vaga
- `status_candidatura` - Para acompanhar status
- `created_at` - Para histórico temporal
- `data_envio` - Para análise de quando candidatou
- Índice composto em `vaga_id + status_candidatura`

---

## 🔄 Fluxo entre Tabelas

```
VAGAS_ANALISADAS                          CANDIDATURAS
        ↓                                       ↑
  (Vaga recebida)                             ↑
        ↓                                       ↑
  (Análise por IA)          ───────────────────┘
        ↓
  score + classificacao
        ↓
    ├─ match_score >= 75
    │  └─→ status_fluxo = 'aprovada_para_candidatura'
    │       └─→ Cria novo registro em CANDIDATURAS
    │           └─→ Executa ou aguarda revisão
    │               └─→ Atualiza status_fluxo = 'candidatura_executada'
    │
    ├─ 55 <= match_score < 75
    │  └─→ status_fluxo = 'revisao_manual'
    │       └─→ Aguarda decisão do usuário
    │           └─→ Se aprovado: cria CANDIDATURA
    │
    └─ match_score < 55
       └─→ status_fluxo = 'descartada'
           └─→ Sem candidatura gerada
```

## 🚀 Como Executar no Supabase

### Passo 1: Acessar Supabase
1. Acesse [supabase.com](https://supabase.com)
2. Faça login ou crie uma conta
3. Crie um novo projeto ou abra um existente

### Passo 2: Abrir SQL Editor
- No dashboard do Supabase, clique em **"SQL Editor"** no menu esquerdo
- Clique em **"New Query"**

### Passo 3: Copiar e Executar o Script
1. Abra o arquivo `database/schema.sql`
2. Selecione todo o conteúdo (Ctrl+A)
3. Copie (Ctrl+C)
4. Cole no SQL Editor do Supabase
5. Clique em **"Run"** (ou Ctrl+Enter)

### Passo 4: Verificar Criação
Após executar, você pode:
- Ir para **"Table Editor"** para ver as tabelas criadas
- Verificar se aparecem `vagas_analisadas` e `candidaturas`
- Conferir os índices criados

### Passo 5: (Opcional) Configurar RLS Policies
No SQL Editor, você pode adicionar Row Level Security policies. Exemplo:

```sql
-- Enable RLS on tables
ALTER TABLE public.vagas_analisadas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidaturas ENABLE ROW LEVEL SECURITY;

-- Create policies (configure conforme sua necessidade)
CREATE POLICY "Enable read for authenticated users" 
  ON public.vagas_analisadas 
  FOR SELECT 
  USING (true);
```

---

## 💡 Por Que Um Banco com Tabelas Separadas?

Algumas opções de design foram consideradas:

### ❌ Separar em Bancos Diferentes
- **Problema:** Mais complexo gerenciar foreign keys entre bancos
- **Problema:** Queries mais lentas (requerem joins entre bancos)
- **Problema:** Mais difícil manter integridade referencial
- **Problema:** Aumenta complexidade operacional

### ✅ Um Banco com Tabelas Separadas (ESCOLHIDO)
- **Vantagem:** Foreign keys diretas entre tabelas
- **Vantagem:** Queries eficientes com índices
- **Vantagem:** Fácil manter integridade (ON DELETE CASCADE)
- **Vantagem:** Simples de backupear tudo junto
- **Vantagem:** RLS policies e autenticação funcionam naturalmente
- **Vantagem:** Performance melhor em análises cruzadas
- **Vantagem:** Escalável para múltiplos usuários/projetos (adiciona user_id depois)

---

## 📝 Detalhes de Implementação

### Ajustes Realizados (v1.1)

**Três melhorias críticas foram implementadas após análise inicial:**

#### 1. CREATE TRIGGER IF NOT EXISTS (Idempotência)
- **Problema resolvido:** Script pode ser executado múltiplas vezes sem falhar
- **Implementação:** `CREATE TRIGGER IF NOT EXISTS` garante que triggers só são criadas uma vez
- **Benefício:** Permite re-execução segura em atualizações futuras
- **Nota:** Removemos `DROP TRIGGER IF EXISTS` para evitar "operações destrutivas" alertadas pelo Supabase

#### 2. Constraint de Consistência (Data Integrity)
- **Problema resolvido:** Banco agora valida relação lógica entre `classificacao`, `should_apply` e `needs_review`
- **Regras implementadas:**
  ```
  classificacao='aplicar'    ⟹ should_apply=true  E needs_review=false
  classificacao='revisar'    ⟹ should_apply=true  E needs_review=true  (Aplicar COM revisão)
  classificacao='descartar'  ⟹ should_apply=false E needs_review=false
  ```
- **Benefício:** Protege integridade mesmo se agente IA cometer erros
- **Implementação:** `CONSTRAINT check_classificacao_consistency` na tabela `vagas_analisadas`

#### 3. Campo raw_response (Auditoria & Debug)
- **Novo campo:** `raw_response jsonb NOT NULL DEFAULT '{}'::jsonb`
- **Propósito:** Armazena resposta completa do Ollama em JSON
- **Benefícios:**
  - Debug de decisões inconsistentes
  - Auditoria completa do agente
  - Permite reprocessamento futuro
  - Base para análises analíticas

### Constraints Implementados
- ✅ `NOT NULL` em campos obrigatórios
- ✅ `CHECK` em enums (classificacao, status_fluxo, status_candidatura)
- ✅ `CHECK` em ranges (match_score 0-100)
- ✅ `UNIQUE` não usada (permite múltiplas análises da mesma vaga)
- ✅ `FOREIGN KEY` com `ON DELETE CASCADE`

### Triggers Automáticos
- ✅ `updated_at` atualizado automaticamente em UPDATE
- ✅ Função `update_updated_at_column()` reutilizável

### Índices para Performance
- ✅ Índices individuais nos campos mais consultados
- ✅ Índices compostos para queries comuns
- ✅ Ordem DESC em timestamps (mais recentes primeiro)

### Dados de Exemplo (para teste)

```sql
-- Inserir uma vaga de teste (classificacao='aplicar')
INSERT INTO public.vagas_analisadas (
    titulo_vaga, empresa, localizacao, modalidade, tipo_vaga,
    texto_bruto_vaga, match_score, classificacao, should_apply, needs_review,
    motivos_match, gaps, status_fluxo, raw_response
) VALUES (
    'Senior Backend Developer',
    'Tech Company XYZ',
    'São Paulo, SP',
    'Remoto',
    'CLT',
    'Procuramos um Senior Backend com 5+ anos...',
    85,
    'aplicar',
    true,
    false,
    '["Stack em Python", "Remoto", "Bom salário"]'::jsonb,
    '["Requer AWS", "Startup early stage"]'::jsonb,
    'aprovada_para_candidatura',
    '{"score": 85, "reasoning": "Excellent match with profile", "model": "qwen2.5:3b"}'::jsonb
);

-- Inserir uma vaga de teste (classificacao='revisar')
INSERT INTO public.vagas_analisadas (
    titulo_vaga, empresa, localizacao, modalidade, tipo_vaga,
    texto_bruto_vaga, match_score, classificacao, should_apply, needs_review,
    motivos_match, gaps, status_fluxo, raw_response
) VALUES (
    'Full Stack Developer',
    'Startup ABC',
    'Belo Horizonte, MG',
    'Presencial',
    'CLT',
    'Procuramos um Full Stack...',
    65,
    'revisar',
    true,
    true,
    '["Tech stack interessante", "Bom crescimento"]'::jsonb,
    '["Presencial requerido", "Foco em APIs RPC"]'::jsonb,
    'revisao_manual',
    '{"score": 65, "reasoning": "Mixed signals, needs manual review", "model": "qwen2.5:3b"}'::jsonb
);

-- Inserir uma vaga de teste (classificacao='descartar')
INSERT INTO public.vagas_analisadas (
    titulo_vaga, empresa, localizacao, modalidade, tipo_vaga,
    texto_bruto_vaga, match_score, classificacao, should_apply, needs_review,
    motivos_match, gaps, status_fluxo, raw_response
) VALUES (
    'Java/Spring Boot Developer',
    'Legacy Corp',
    'Rio de Janeiro, RJ',
    'Presencial',
    'CLT',
    'Procuramos expertise em Java/Spring Boot...',
    32,
    'descartar',
    false,
    false,
    '["Trabalho estável"]'::jsonb,
    '["Stack Java não preferida", "Presencial obrigatório", "Legacy codebase"]'::jsonb,
    'descartada',
    '{"score": 32, "reasoning": "Poor match with preferences", "model": "qwen2.5:3b"}'::jsonb
);

-- Inserir uma candidatura para a primeira vaga
INSERT INTO public.candidaturas (
    vaga_id,
    status_candidatura,
    curriculo_usado,
    payload_candidatura
) SELECT
    id,
    'pendente',
    'curriculo_v3.pdf',
    '{"nome": "Gabriel", "email": "gabriel@example.com", "phone": "+55 11 99999-9999"}'::jsonb
FROM public.vagas_analisadas
WHERE empresa = 'Tech Company XYZ'
LIMIT 1;

-- Query para validar consistência:
-- As linhas abaixo devem retornar vazio (sem violações)
SELECT id, classificacao, should_apply, needs_review
FROM public.vagas_analisadas
WHERE NOT (
    (classificacao = 'aplicar' AND should_apply = true AND needs_review = false)
    OR
    (classificacao = 'revisar' AND should_apply = true AND needs_review = true)
    OR
    (classificacao = 'descartar' AND should_apply = false AND needs_review = false)
);
```

---

## 🔧 Próximos Passos

Após executar este schema, os próximos passos serão:

1. **Etapa 7:** Integrar Supabase com n8n (supabase-rest ou supabase-client)
2. **Etapa 11:** Criar funções para geração de conteúdo de candidatura
3. **Etapa 12:** Implementar automação de candidatura
4. **Etapa 14:** Criar dashboard com SQL queries
5. **Etapa 15:** Adicionar autenticação e RLS policies

---

## 📞 Suporte

Para dúvidas:
- Consulte a documentação do Supabase: [supabase.com/docs](https://supabase.com/docs)
- Verifique os logs no Supabase Dashboard
- Teste queries no SQL Editor antes de integrar com código

---

**Última atualização:** Abril 2026
