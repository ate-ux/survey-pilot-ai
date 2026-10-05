"""Client HTTP centralisé pour communiquer avec le backend FastAPI."""
import os
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
TIMEOUT = 300


class APIClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or BACKEND_URL

    def _headers(self):
        token = st.session_state.get("token")
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _handle(self, resp):
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            return None, f"[{resp.status_code}] {detail}"
        try:
            return resp.json(), None
        except Exception:
            return resp.text, None

    # ---------------- Auth ----------------
    def login(self, username: str, password: str):
        r = requests.post(
            f"{self.base_url}/api/auth/login",
            data={"username": username, "password": password},
            timeout=TIMEOUT,
        )
        return self._handle(r)

    def me(self):
        r = requests.get(f"{self.base_url}/api/auth/me", headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Dashboard ----------------
    def kpis(self):
        r = requests.get(f"{self.base_url}/api/dashboard/kpis", headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Projects ----------------
    def list_projects(self):
        r = requests.get(f"{self.base_url}/api/projects", headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def create_project(self, code: str, name: str, description: str = ""):
        r = requests.post(
            f"{self.base_url}/api/projects",
            json={"code": code, "name": name, "description": description},
            headers=self._headers(),
            timeout=TIMEOUT,
        )
        return self._handle(r)

    def update_project(self, project_id: int, data: dict):
        r = requests.patch(
            f"{self.base_url}/api/projects/{project_id}",
            json=data, headers=self._headers(), timeout=TIMEOUT,
        )
        return self._handle(r)

    def delete_project(self, project_id: int):
        r = requests.delete(
            f"{self.base_url}/api/projects/{project_id}",
            headers=self._headers(), timeout=TIMEOUT,
        )
        return self._handle(r)

    # ---------------- Surveys ----------------
    def list_surveys(self, project_id: int = None):
        params = {"project_id": project_id} if project_id else {}
        r = requests.get(f"{self.base_url}/api/surveys", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def create_survey(self, project_id: int, code: str, title: str, **kwargs):
        payload = {"project_id": project_id, "code": code, "title": title, **kwargs}
        r = requests.post(f"{self.base_url}/api/surveys", json=payload,
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def get_survey(self, survey_id: int):
        r = requests.get(f"{self.base_url}/api/surveys/{survey_id}",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Questions ----------------
    def list_questions(self, survey_id: int):
        r = requests.get(f"{self.base_url}/api/questions", params={"survey_id": survey_id},
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def create_question(self, survey_id: int, order_index: int, code: str,
                        label: str, question_type: str, options=None, is_required=True):
        payload = {
            "survey_id": survey_id,
            "order_index": order_index,
            "code": code,
            "label": label,
            "question_type": question_type,
            "options": options,
            "is_required": is_required,
        }
        r = requests.post(f"{self.base_url}/api/questions", json=payload,
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Responses ----------------
    def list_responses(self, survey_id: int = None):
        params = {"survey_id": survey_id} if survey_id else {}
        r = requests.get(f"{self.base_url}/api/responses", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def seed_responses(self, survey_id: int, count: int = 200):
        r = requests.post(f"{self.base_url}/api/seed/responses/{survey_id}",
                          params={"count": count},
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Analysis ----------------
    def descriptive(self, survey_id: int, question_code: str):
        r = requests.get(f"{self.base_url}/api/analysis/descriptive/{survey_id}",
                         params={"question_code": question_code},
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def bivariate(self, survey_id: int, x_code: str, y_code: str):
        r = requests.get(f"{self.base_url}/api/analysis/bivariate/{survey_id}",
                         params={"x_code": x_code, "y_code": y_code},
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def regression(self, survey_id: int, x_code: str, y_code: str):
        r = requests.get(f"{self.base_url}/api/analysis/regression/{survey_id}",
                         params={"x_code": x_code, "y_code": y_code},
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def analysis_questions(self, survey_id: int):
        r = requests.get(f"{self.base_url}/api/analysis/questions/{survey_id}",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- AI Agents ----------------
    def list_agents(self):
        r = requests.get(f"{self.base_url}/api/ai/agents", headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def methodologue_propose(self, survey_id: int):
        r = requests.post(f"{self.base_url}/api/ai/methodologue/propose/{survey_id}",
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def echantillonneur_propose(self, survey_id: int, confidence: float = 0.95, margin: float = 0.05):
        r = requests.post(f"{self.base_url}/api/ai/echantillonneur/propose/{survey_id}",
                          params={"confidence": confidence, "margin": margin},
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def list_proposals(self, status: str = None):
        params = {"status": status} if status else {}
        r = requests.get(f"{self.base_url}/api/ai/proposals", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def decide_proposal(self, proposal_id: int, decision: str, note: str = ""):
        r = requests.post(f"{self.base_url}/api/ai/proposals/{proposal_id}/decide",
                          json={"decision": decision, "decision_note": note},
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def list_ai_actions(self, limit: int = 50):
        r = requests.get(f"{self.base_url}/api/ai/actions", params={"limit": limit},
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Audit ----------------
    def list_audit(self, limit: int = 100):
        r = requests.get(f"{self.base_url}/api/audit", params={"limit": limit},
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Sandbox ----------------
    def sandbox_stats(self):
        r = requests.get(f"{self.base_url}/api/sandbox/stats", headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def sandbox_clone(self, project_id: int):
        r = requests.post(f"{self.base_url}/api/sandbox/clone/{project_id}",
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def sandbox_reset(self):
        r = requests.delete(f"{self.base_url}/api/sandbox/reset",
                            headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Versions ----------------
    def list_versions(self, survey_id: int):
        r = requests.get(f"{self.base_url}/api/versions/survey/{survey_id}",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def snapshot_survey(self, survey_id: int):
        r = requests.post(f"{self.base_url}/api/versions/survey/{survey_id}/snapshot",
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def restore_version(self, survey_id: int, version_number: int):
        r = requests.post(
            f"{self.base_url}/api/versions/survey/{survey_id}/restore/{version_number}",
            headers=self._headers(), timeout=TIMEOUT,
        )
        return self._handle(r)

    # ---------------- Sampling ----------------
    def create_sampling_plan(self, survey_id: int, method: str = "simple_random",
                             sample_size: int = None, confidence: float = 0.95, margin: float = 0.05):
        r = requests.post(
            f"{self.base_url}/api/sampling/plan/{survey_id}",
            params={"method": method, "sample_size": sample_size,
                    "confidence": confidence, "margin": margin},
            headers=self._headers(), timeout=TIMEOUT,
        )
        return self._handle(r)

    def list_sampling_plans(self, survey_id: int):
        r = requests.get(f"{self.base_url}/api/sampling/plan/{survey_id}",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def draw_sample(self, population_size: int, sample_size: int, seed: int = None):
        params = {"population_size": population_size, "sample_size": sample_size}
        if seed is not None:
            params["seed"] = seed
        r = requests.post(f"{self.base_url}/api/sampling/draw", params=params,
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Knowledge ----------------
    def list_knowledge(self, category: str = None):
        params = {"category": category} if category else {}
        r = requests.get(f"{self.base_url}/api/knowledge", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def seed_knowledge(self):
        r = requests.post(f"{self.base_url}/api/knowledge/seed",
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- Profile ----------------
    def get_profile(self):
        r = requests.get(f"{self.base_url}/api/profile/me", headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def update_profile(self, full_name=None, email=None):
        payload = {}
        if full_name is not None:
            payload["full_name"] = full_name
        if email is not None:
            payload["email"] = email
        r = requests.patch(f"{self.base_url}/api/profile/me", json=payload,
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def change_password(self, current_password, new_password):
        r = requests.post(f"{self.base_url}/api/profile/change-password",
                          json={"current_password": current_password,
                                "new_password": new_password},
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def delete_avatar(self):
        r = requests.delete(f"{self.base_url}/api/profile/avatar",
                            headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def list_all_users(self):
        r = requests.get(f"{self.base_url}/api/profile/users",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def create_user(self, username, email, password, full_name=None, role_id=1):
        r = requests.post(f"{self.base_url}/api/profile/users",
                          json={"username": username, "email": email,
                                "password": password, "full_name": full_name,
                                "role_id": role_id},
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def delete_user(self, user_id):
        r = requests.delete(f"{self.base_url}/api/profile/users/{user_id}",
                            headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def toggle_user_active(self, user_id):
        r = requests.patch(f"{self.base_url}/api/profile/users/{user_id}/toggle-active",
                           headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- ML ----------------
    def detect_anomalies(self, survey_id, contamination=0.05):
        r = requests.get(f"{self.base_url}/api/ml/detect-anomalies/{survey_id}",
                         params={"contamination": contamination},
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def predict_nonresponse(self, survey_id):
        r = requests.get(f"{self.base_url}/api/ml/predict-nonresponse/{survey_id}",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def data_profile(self, survey_id):
        r = requests.get(f"{self.base_url}/api/ml/profile/{survey_id}",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)
    # ---------------- Géo ----------------
    def get_map_data(self, survey_id=None):
        params = {"survey_id": survey_id} if survey_id else {}
        r = requests.get(f"{self.base_url}/api/geo/map-data", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def get_geo_zones(self, zone_type=None):
        params = {"zone_type": zone_type} if zone_type else {}
        r = requests.get(f"{self.base_url}/api/geo/zones", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def create_geo_zone(self, name, zone_type, center_lat, center_lon):
        r = requests.post(f"{self.base_url}/api/geo/zones",
                          json={"name": name, "zone_type": zone_type,
                                "center_lat": center_lat, "center_lon": center_lon},
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def get_geo_stats(self, survey_id=None):
        params = {"survey_id": survey_id} if survey_id else {}
        r = requests.get(f"{self.base_url}/api/geo/stats", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    # ---------------- LLM ----------------
    def get_llm_status(self):
        r = requests.get(f"{self.base_url}/api/llm/status",
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def get_llm_recommendations(self, survey_id):
        r = requests.post(f"{self.base_url}/api/llm/recommend/{survey_id}",
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def get_llm_interpretation(self, survey_id):
        r = requests.post(f"{self.base_url}/api/llm/interpret/{survey_id}",
                          headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)

    def list_llm_recommendations(self, survey_id=None):
        params = {"survey_id": survey_id} if survey_id else {}
        r = requests.get(f"{self.base_url}/api/llm/recommendations", params=params,
                         headers=self._headers(), timeout=TIMEOUT)
        return self._handle(r)


@st.cache_resource
def get_client():
    return APIClient()