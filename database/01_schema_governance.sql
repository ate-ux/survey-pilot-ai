-- ============================================================
-- SurveyPilot AI V2 - Schéma complet
-- Gouvernance, projets, enquêtes, collecte, audit, versioning
-- ============================================================

-- ============================================================
-- 1. GOUVERNANCE : Utilisateurs, rôles, permissions
-- ============================================================

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    avatar_url VARCHAR(255),
    role_id INTEGER REFERENCES roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(80) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- ============================================================
-- 2. ENVIRONNEMENTS : Réel vs Sandbox
-- ============================================================

CREATE TABLE IF NOT EXISTS environments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    is_sandbox BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 3. PROJETS
-- ============================================================

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    status VARCHAR(30) DEFAULT 'active',
    environment_id INTEGER REFERENCES environments(id),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 4. ENQUÊTES ET QUESTIONNAIRES
-- ============================================================

CREATE TABLE IF NOT EXISTS surveys (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    code VARCHAR(30) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(30) DEFAULT 'draft',
    target_population INTEGER,
    sample_size INTEGER,
    start_date DATE,
    end_date DATE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, code)
);

CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    survey_id INTEGER REFERENCES surveys(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    code VARCHAR(30) NOT NULL,
    label TEXT NOT NULL,
    question_type VARCHAR(30) NOT NULL,
    options JSONB,
    is_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (survey_id, code)
);

-- ============================================================
-- 5. ÉCHANTILLONNAGE
-- ============================================================

CREATE TABLE IF NOT EXISTS sampling_plans (
    id SERIAL PRIMARY KEY,
    survey_id INTEGER REFERENCES surveys(id) ON DELETE CASCADE,
    method VARCHAR(50) NOT NULL,
    strata JSONB,
    sample_size INTEGER,
    confidence_level NUMERIC(5,2),
    margin_error NUMERIC(5,2),
    notes TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 6. ENQUÊTEURS ET COLLECTE
-- ============================================================

CREATE TABLE IF NOT EXISTS interviewers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    code VARCHAR(30) UNIQUE NOT NULL,
    zone VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS responses (
    id SERIAL PRIMARY KEY,
    survey_id INTEGER REFERENCES surveys(id) ON DELETE CASCADE,
    interviewer_id INTEGER REFERENCES interviewers(id),
    respondent_code VARCHAR(50),
    status VARCHAR(30) DEFAULT 'collected',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    environment_id INTEGER REFERENCES environments(id)
);

CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,
    response_id INTEGER REFERENCES responses(id) ON DELETE CASCADE,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 7. ANOMALIES / CAP (Contrôle Qualité)
-- ============================================================

CREATE TABLE IF NOT EXISTS anomalies (
    id SERIAL PRIMARY KEY,
    response_id INTEGER REFERENCES responses(id) ON DELETE CASCADE,
    anomaly_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',
    description TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- ============================================================
-- 8. WORKFLOW DE VALIDATION (Approbations)
-- ============================================================

CREATE TABLE IF NOT EXISTS proposals (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    survey_id INTEGER REFERENCES surveys(id),
    proposal_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',
    proposed_by INTEGER REFERENCES users(id),
    proposed_by_ai BOOLEAN DEFAULT FALSE,
    decided_by INTEGER REFERENCES users(id),
    decision_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP
);

-- ============================================================
-- 9. AGENTS IA
-- ============================================================

CREATE TABLE IF NOT EXISTS ai_agents (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    autonomy_level VARCHAR(30) DEFAULT 'supervised',
    is_enabled BOOLEAN DEFAULT TRUE,
    config JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_actions (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES ai_agents(id),
    proposal_id INTEGER REFERENCES proposals(id),
    action_type VARCHAR(50),
    input_data JSONB,
    output_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 10. VERSIONING
-- ============================================================

CREATE TABLE IF NOT EXISTS versions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entity_type, entity_id, version_number)
);

-- ============================================================
-- 11. JOURNAL D'AUDIT
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 12. BASE DE CONNAISSANCES
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(80),
    content TEXT,
    tags JSONB,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEX
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_projects_code ON projects(code);
CREATE INDEX IF NOT EXISTS idx_surveys_project ON surveys(project_id);
CREATE INDEX IF NOT EXISTS idx_questions_survey ON questions(survey_id);
CREATE INDEX IF NOT EXISTS idx_responses_survey ON responses(survey_id);
CREATE INDEX IF NOT EXISTS idx_answers_response ON answers(response_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);

-- ============================================================
-- DONNÉES INITIALES
-- ============================================================

-- Rôles
INSERT INTO roles (name, description) VALUES
    ('super_admin', 'Super administrateur - accès total'),
    ('manager', 'Gestionnaire de projet'),
    ('analyst', 'Analyste statistique'),
    ('interviewer', 'Enquêteur de terrain')
ON CONFLICT (name) DO NOTHING;

-- Environnements
INSERT INTO environments (name, is_sandbox) VALUES
    ('production', FALSE),
    ('sandbox', TRUE)
ON CONFLICT (name) DO NOTHING;

-- Permissions de base
INSERT INTO permissions (code, description) VALUES
    ('project.create', 'Créer un projet'),
    ('project.read', 'Consulter un projet'),
    ('project.update', 'Modifier un projet'),
    ('project.delete', 'Supprimer un projet'),
    ('survey.create', 'Créer une enquête'),
    ('survey.validate', 'Valider une enquête'),
    ('data.collect', 'Collecter des données'),
    ('data.export', 'Exporter des données'),
    ('ai.configure', 'Configurer les agents IA'),
    ('sandbox.reset', 'Réinitialiser le sandbox'),
    ('user.manage', 'Gérer les utilisateurs')
ON CONFLICT (code) DO NOTHING;

-- Agents IA initiaux
INSERT INTO ai_agents (code, name, agent_type, autonomy_level) VALUES
    ('methodologue', 'Agent Méthodologue', 'planner', 'supervised'),
    ('echantillonneur', 'Agent Échantillonneur', 'sampler', 'supervised')
ON CONFLICT (code) DO NOTHING;