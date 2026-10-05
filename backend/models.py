from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date,
    DateTime, Numeric, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120))
    avatar_url = Column(String(255))
    role_id = Column(Integer, ForeignKey("roles.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime)


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    code = Column(String(80), unique=True, nullable=False)
    description = Column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)


class Environment(Base):
    __tablename__ = "environments"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    is_sandbox = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text)
    status = Column(String(30), default="active")
    environment_id = Column(Integer, ForeignKey("environments.id"))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    code = Column(String(30), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(30), default="draft")
    target_population = Column(Integer)
    sample_size = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"))
    order_index = Column(Integer, nullable=False)
    code = Column(String(30), nullable=False)
    label = Column(Text, nullable=False)
    question_type = Column(String(30), nullable=False)
    options = Column(JSONB)
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("survey_id", "code"),)


class SamplingPlan(Base):
    __tablename__ = "sampling_plans"
    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"))
    method = Column(String(50), nullable=False)
    strata = Column(JSONB)
    sample_size = Column(Integer)
    confidence_level = Column(Numeric(5, 2))
    margin_error = Column(Numeric(5, 2))
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())


class Interviewer(Base):
    __tablename__ = "interviewers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    code = Column(String(30), unique=True, nullable=False)
    zone = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Response(Base):
    __tablename__ = "responses"
    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"))
    interviewer_id = Column(Integer, ForeignKey("interviewers.id"))
    respondent_code = Column(String(50))
    status = Column(String(30), default="collected")
    collected_at = Column(DateTime, server_default=func.now())
    environment_id = Column(Integer, ForeignKey("environments.id"))
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    gps_accuracy = Column(Numeric(6, 2))
    collected_at_gps = Column(DateTime)


class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey("responses.id", ondelete="CASCADE"))
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"))
    value = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class Anomaly(Base):
    __tablename__ = "anomalies"
    id = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey("responses.id", ondelete="CASCADE"))
    anomaly_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="medium")
    description = Column(Text)
    resolved = Column(Boolean, default=False)
    detected_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)


class Proposal(Base):
    __tablename__ = "proposals"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    survey_id = Column(Integer, ForeignKey("surveys.id"))
    proposal_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(30), default="pending")
    proposed_by = Column(Integer, ForeignKey("users.id"))
    proposed_by_ai = Column(Boolean, default=False)
    decided_by = Column(Integer, ForeignKey("users.id"))
    decision_note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    decided_at = Column(DateTime)


class AIAgent(Base):
    __tablename__ = "ai_agents"
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    agent_type = Column(String(50), nullable=False)
    autonomy_level = Column(String(30), default="supervised")
    is_enabled = Column(Boolean, default=True)
    config = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())


class AIAction(Base):
    __tablename__ = "ai_actions"
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id"))
    proposal_id = Column(Integer, ForeignKey("proposals.id"))
    action_type = Column(String(50))
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())


class Version(Base):
    __tablename__ = "versions"
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSONB, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "version_number"),)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(80), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    details = Column(JSONB)
    ip_address = Column(String(45))
    created_at = Column(DateTime, server_default=func.now())


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    category = Column(String(80))
    content = Column(Text)
    tags = Column(JSONB)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


# ============================================================
# V2.1 - Géolocalisation
# ============================================================

class GeoZone(Base):
    __tablename__ = "geo_zones"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    zone_type = Column(String(50))
    geometry = Column(JSONB)
    center_lat = Column(Numeric(10, 7))
    center_lon = Column(Numeric(10, 7))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())


class InterviewerLocation(Base):
    __tablename__ = "interviewer_locations"
    id = Column(Integer, primary_key=True)
    interviewer_id = Column(Integer, ForeignKey("interviewers.id"))
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    recorded_at = Column(DateTime, server_default=func.now())


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"))
    recommendation_type = Column(String(50))
    content = Column(Text)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime, server_default=func.now())