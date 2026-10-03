from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime, date


# --- Auth ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role_id: Optional[int] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role_id: Optional[int] = None
    is_active: bool
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Profile ---
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class AdminUserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role_id: Optional[int] = 1


# --- Projects ---
class ProjectCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    environment_id: Optional[int] = 1


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    status: str
    environment_id: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True


# --- Surveys ---
class SurveyCreate(BaseModel):
    project_id: int
    code: str
    title: str
    description: Optional[str] = None
    target_population: Optional[int] = None
    sample_size: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class SurveyOut(BaseModel):
    id: int
    project_id: int
    code: str
    title: str
    description: Optional[str] = None
    status: str
    target_population: Optional[int] = None
    sample_size: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True


# --- Questions ---
class QuestionCreate(BaseModel):
    survey_id: int
    order_index: int
    code: str
    label: str
    question_type: str
    options: Optional[Any] = None
    is_required: bool = True


class QuestionOut(BaseModel):
    id: int
    survey_id: int
    order_index: int
    code: str
    label: str
    question_type: str
    options: Optional[Any] = None
    is_required: bool
    class Config:
        from_attributes = True


# --- Responses ---
class AnswerCreate(BaseModel):
    question_id: int
    value: str


class ResponseCreate(BaseModel):
    survey_id: int
    interviewer_id: Optional[int] = None
    respondent_code: Optional[str] = None
    answers: List[AnswerCreate] = []


class AnswerOut(BaseModel):
    id: int
    question_id: int
    value: Optional[str] = None
    class Config:
        from_attributes = True


class ResponseOut(BaseModel):
    id: int
    survey_id: int
    respondent_code: Optional[str] = None
    status: str
    collected_at: datetime
    class Config:
        from_attributes = True


# --- Proposals ---
class ProposalCreate(BaseModel):
    project_id: Optional[int] = None
    survey_id: Optional[int] = None
    proposal_type: str
    payload: Any
    proposed_by_ai: bool = False


class ProposalDecision(BaseModel):
    decision: str
    decision_note: Optional[str] = None


class ProposalOut(BaseModel):
    id: int
    project_id: Optional[int] = None
    survey_id: Optional[int] = None
    proposal_type: str
    payload: Any
    status: str
    proposed_by_ai: bool
    created_at: datetime
    class Config:
        from_attributes = True


# --- AI ---
class AIAgentOut(BaseModel):
    id: int
    code: str
    name: str
    agent_type: str
    autonomy_level: str
    is_enabled: bool
    class Config:
        from_attributes = True


# --- Audit ---
class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


ResponseCreate.model_rebuild()