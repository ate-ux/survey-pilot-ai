-- ============================================================
-- Migration V2.1 - Géolocalisation + LLM
-- ============================================================

-- 1. Coordonnées GPS sur les réponses
ALTER TABLE responses ADD COLUMN IF NOT EXISTS latitude NUMERIC(10, 7);
ALTER TABLE responses ADD COLUMN IF NOT EXISTS longitude NUMERIC(10, 7);
ALTER TABLE responses ADD COLUMN IF NOT EXISTS gps_accuracy NUMERIC(6, 2);
ALTER TABLE responses ADD COLUMN IF NOT EXISTS collected_at_gps TIMESTAMP;

-- 2. Zones géographiques (ISSEA, quartiers, régions)
CREATE TABLE IF NOT EXISTS geo_zones (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    zone_type VARCHAR(50),
    geometry JSONB,
    center_lat NUMERIC(10, 7),
    center_lon NUMERIC(10, 7),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tracking enquêteurs
CREATE TABLE IF NOT EXISTS interviewer_locations (
    id SERIAL PRIMARY KEY,
    interviewer_id INTEGER REFERENCES interviewers(id),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Recommandations IA
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id SERIAL PRIMARY KEY,
    survey_id INTEGER REFERENCES surveys(id) ON DELETE CASCADE,
    recommendation_type VARCHAR(50),
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Provider LLM sur les agents IA
ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS provider VARCHAR(50);
ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);

-- 6. Métadonnées LLM sur les propositions
ALTER TABLE proposals ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100);
ALTER TABLE proposals ADD COLUMN IF NOT EXISTS llm_tokens INTEGER;

-- 7. Index
CREATE INDEX IF NOT EXISTS idx_responses_geo ON responses(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_geo_zones_type ON geo_zones(zone_type);
CREATE INDEX IF NOT EXISTS idx_recommendations_survey ON ai_recommendations(survey_id);
CREATE INDEX IF NOT EXISTS idx_interviewer_locations_interv ON interviewer_locations(interviewer_id);

-- 8. Zone ISSEA par défaut (position approximative ISSEA Yaoundé)
INSERT INTO geo_zones (name, zone_type, center_lat, center_lon)
SELECT 'ISSEA Yaoundé', 'issea', 3.8480, 11.5021
WHERE NOT EXISTS (SELECT 1 FROM geo_zones WHERE zone_type = 'issea');