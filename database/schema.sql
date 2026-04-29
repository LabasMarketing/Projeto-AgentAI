-- ============================================================
-- Agent IA - Database Schema
-- Supabase SQL Schema for Job Analysis and Application System
-- ============================================================
-- Created: April 2026
-- Purpose: Store analyzed jobs and application records
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. TABELA: vagas_analisadas
-- Stores the results of AI agent analysis on job postings
-- ============================================================

CREATE TABLE IF NOT EXISTS public.vagas_analisadas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Job information
    titulo_vaga text NOT NULL,
    empresa text NOT NULL,
    localizacao text,
    modalidade text,
    tipo_vaga text,
    texto_bruto_vaga text NOT NULL,
    url_vaga text,
    fonte_vaga text,
    
    -- Analysis results
    match_score integer NOT NULL CHECK (match_score >= 0 AND match_score <= 100),
    classificacao text NOT NULL CHECK (classificacao IN ('aplicar', 'revisar', 'descartar')),
    should_apply boolean NOT NULL,
    needs_review boolean NOT NULL,
    
    -- Detailed analysis
    motivos_match jsonb NOT NULL DEFAULT '[]'::jsonb,
    gaps jsonb NOT NULL DEFAULT '[]'::jsonb,
    resumo_personalizado text,
    raw_response jsonb NOT NULL DEFAULT '{}'::jsonb,
    
    -- Workflow status
    status_fluxo text NOT NULL DEFAULT 'analisada' CHECK (
        status_fluxo IN (
            'analisada',
            'aprovada_para_candidatura',
            'descartada',
            'revisao_manual',
            'candidatura_executada',
            'erro'
        )
    ),
    
    -- Timestamps
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    
    -- Consistency constraints
    CONSTRAINT check_classificacao_consistency CHECK (
        (
            -- Se classificacao='aplicar': deve ter should_apply=true e needs_review=false
            (classificacao = 'aplicar' AND should_apply = true AND needs_review = false)
            OR
            -- Se classificacao='revisar': deve ter needs_review=true e should_apply=true (aplicar com revisão)
            (classificacao = 'revisar' AND needs_review = true AND should_apply = true)
            OR
            -- Se classificacao='descartar': deve ter should_apply=false e needs_review=false
            (classificacao = 'descartar' AND should_apply = false AND needs_review = false)
        )
    )
);

-- Add comments to vagas_analisadas table
COMMENT ON TABLE public.vagas_analisadas IS 'Stores AI analysis results for job postings. Each record represents one analyzed job with its score, classification, and reasoning.';
COMMENT ON COLUMN public.vagas_analisadas.id IS 'Unique identifier for the analyzed job record';
COMMENT ON COLUMN public.vagas_analisadas.match_score IS 'Adherence score from 0 to 100, where higher means better match with candidate profile';
COMMENT ON COLUMN public.vagas_analisadas.classificacao IS 'AI recommendation: aplicar (apply), revisar (review), or descartar (discard)';
COMMENT ON COLUMN public.vagas_analisadas.raw_response IS 'Complete JSON response from the AI agent (Ollama) for debugging and auditing purposes';
COMMENT ON COLUMN public.vagas_analisadas.status_fluxo IS 'Current workflow status tracking the progression through the system';

-- ============================================================
-- 2. TABELA: candidaturas
-- Stores application records generated or executed by the system
-- ============================================================

CREATE TABLE IF NOT EXISTS public.candidaturas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign key to analyzed job
    vaga_id uuid NOT NULL REFERENCES public.vagas_analisadas(id) ON DELETE CASCADE,
    
    -- Application status and content
    status_candidatura text NOT NULL DEFAULT 'pendente' CHECK (
        status_candidatura IN (
            'pendente',
            'em_revisao',
            'enviada',
            'falhou',
            'cancelada'
        )
    ),
    
    -- Application details
    mensagem_enviada text,
    curriculo_usado text,
    payload_candidatura jsonb NOT NULL DEFAULT '{}'::jsonb,
    retorno_site text,
    observacoes text,
    data_envio timestamptz,
    
    -- Timestamps
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Add comments to candidaturas table
COMMENT ON TABLE public.candidaturas IS 'Stores application records created or executed by the system for approved jobs. Links to vagas_analisadas via vaga_id.';
COMMENT ON COLUMN public.candidaturas.vaga_id IS 'Reference to the job posting in vagas_analisadas table';
COMMENT ON COLUMN public.candidaturas.status_candidatura IS 'Current status of the application: pendente (pending), em_revisao (under review), enviada (sent), falhou (failed), or cancelada (cancelled)';
COMMENT ON COLUMN public.candidaturas.payload_candidatura IS 'JSON payload with application details, form fields submitted, and metadata';

-- ============================================================
-- 3. FUNÇÃO: update_updated_at_column
-- Automatically updates the updated_at timestamp
-- ============================================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.update_updated_at_column() IS 'Trigger function to automatically set updated_at column to current timestamp on UPDATE operations';

-- ============================================================
-- 4. TRIGGERS: updated_at
-- ============================================================

-- Create trigger for vagas_analisadas (safe approach)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers 
        WHERE trigger_name = 'update_vagas_analisadas_updated_at'
    ) THEN
        CREATE TRIGGER update_vagas_analisadas_updated_at
            BEFORE UPDATE ON public.vagas_analisadas
            FOR EACH ROW
            EXECUTE FUNCTION public.update_updated_at_column();
    END IF;
END $$;

-- Create trigger for candidaturas (safe approach)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers 
        WHERE trigger_name = 'update_candidaturas_updated_at'
    ) THEN
        CREATE TRIGGER update_candidaturas_updated_at
            BEFORE UPDATE ON public.candidaturas
            FOR EACH ROW
            EXECUTE FUNCTION public.update_updated_at_column();
    END IF;
END $$;

-- ============================================================
-- 5. INDEXES: Performance optimization
-- ============================================================

-- Indexes on vagas_analisadas
CREATE INDEX IF NOT EXISTS idx_vagas_match_score 
    ON public.vagas_analisadas(match_score DESC);

CREATE INDEX IF NOT EXISTS idx_vagas_classificacao 
    ON public.vagas_analisadas(classificacao);

CREATE INDEX IF NOT EXISTS idx_vagas_status_fluxo 
    ON public.vagas_analisadas(status_fluxo);

CREATE INDEX IF NOT EXISTS idx_vagas_empresa 
    ON public.vagas_analisadas(empresa);

CREATE INDEX IF NOT EXISTS idx_vagas_created_at 
    ON public.vagas_analisadas(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vagas_should_apply 
    ON public.vagas_analisadas(should_apply);

CREATE INDEX IF NOT EXISTS idx_vagas_needs_review 
    ON public.vagas_analisadas(needs_review);

-- Indexes on candidaturas
CREATE INDEX IF NOT EXISTS idx_candidaturas_vaga_id 
    ON public.candidaturas(vaga_id);

CREATE INDEX IF NOT EXISTS idx_candidaturas_status 
    ON public.candidaturas(status_candidatura);

CREATE INDEX IF NOT EXISTS idx_candidaturas_created_at 
    ON public.candidaturas(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidaturas_data_envio 
    ON public.candidaturas(data_envio DESC);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_vagas_fluxo_score 
    ON public.vagas_analisadas(status_fluxo, match_score DESC);

CREATE INDEX IF NOT EXISTS idx_candidaturas_vaga_status 
    ON public.candidaturas(vaga_id, status_candidatura);

-- ============================================================
-- 6. GRANT PERMISSIONS (Optional - adjust as needed)
-- ============================================================

-- If using Row Level Security (RLS), configure here
-- For now, tables are accessible to authenticated users
-- Configure RLS policies in Supabase dashboard as needed

-- ============================================================
-- End of Schema
-- ============================================================
