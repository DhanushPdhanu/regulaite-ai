-- RegulAIte — Supabase Schema
-- Run this in the Supabase SQL editor.
-- Safe to re-run: drops all tables first.

-- Drop tables if re-running migration
DROP TABLE IF EXISTS fixed_clauses CASCADE;
DROP TABLE IF EXISTS citation_results CASCADE;
DROP TABLE IF EXISTS compliance_violations CASCADE;
DROP TABLE IF EXISTS contradictions CASCADE;
DROP TABLE IF EXISTS clauses CASCADE;
DROP TABLE IF EXISTS analysis_results CASCADE;
DROP TABLE IF EXISTS documents CASCADE;

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    filename        TEXT NOT NULL,
    clause_count    INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'UPLOADED'
    -- status values: UPLOADED, ANALYSED, EXPORTED
);

CREATE TABLE clauses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    clause_id       TEXT NOT NULL,       -- e.g. "clause_1_1"
    clause_number   TEXT NOT NULL,       -- e.g. "1.1"
    page_number     INTEGER NOT NULL,
    section         TEXT NOT NULL,
    text            TEXT NOT NULL,
    risk_score      INTEGER DEFAULT 0,
    risk_reason     TEXT,
    flags           TEXT[]               -- e.g. {"CONTRADICTION","GDPR_VIOLATION"}
);

CREATE TABLE analysis_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID REFERENCES documents(id) ON DELETE CASCADE UNIQUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    overall_risk_score  INTEGER,
    risk_label          TEXT,
    hallucination_rate  NUMERIC(5,4),
    citation_graph      JSONB,
    raw_result          JSONB           -- full response cached here
);

CREATE TABLE contradictions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID REFERENCES documents(id) ON DELETE CASCADE,
    clause_id_a         TEXT NOT NULL,
    clause_id_b         TEXT NOT NULL,
    contradiction_type  TEXT NOT NULL,
    explanation         TEXT,
    z3_proof            TEXT
);

CREATE TABLE compliance_violations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    clause_id       TEXT NOT NULL,
    violation_type  TEXT NOT NULL,
    description     TEXT,
    severity        TEXT
);

CREATE TABLE citation_results (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id           UUID REFERENCES documents(id) ON DELETE CASCADE,
    claim                 TEXT NOT NULL,
    source_clause_id      TEXT,
    source_page           INTEGER,
    source_text_excerpt   TEXT,
    confidence_score      NUMERIC(4,3),
    verified              BOOLEAN DEFAULT FALSE
);

CREATE TABLE fixed_clauses (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID REFERENCES documents(id) ON DELETE CASCADE,
    clause_id         TEXT NOT NULL,
    original_text     TEXT NOT NULL,
    fixed_text        TEXT NOT NULL,
    fix_explanation   TEXT
);
