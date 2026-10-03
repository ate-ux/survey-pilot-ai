"""
Agents IA basés sur des règles métier (pas de LLM externe).
- MethodologueAgent : propose un plan de sondage
- EchantillonneurAgent : calcule la taille d'échantillon optimale
"""
import math
from typing import Dict, Any


class MethodologueAgent:
    """Analyse une enquête et propose un plan de sondage."""

    code = "methodologue"
    name = "Agent Méthodologue"

    def propose_plan(self, survey: Dict[str, Any]) -> Dict[str, Any]:
        target = survey.get("target_population") or 1000
        sample = survey.get("sample_size") or self._default_sample(target)

        # Choix de méthode selon taille de population
        if target <= 500:
            method = "exhaustive"
            rationale = "Population < 500 → recensement exhaustif recommandé."
        elif target <= 10000:
            method = "simple_random"
            rationale = "Population moyenne → tirage aléatoire simple."
        else:
            method = "stratified"
            rationale = "Population large → stratification recommandée (par zone, âge, etc.)."

        confidence = 0.95
        margin = self._margin_of_error(sample, target)

        return {
            "method": method,
            "sample_size": sample,
            "confidence_level": confidence,
            "margin_error": round(margin, 4),
            "target_population": target,
            "rationale": rationale,
            "recommendations": [
                "Prévoir 10% de sur-échantillonnage pour non-réponse.",
                "Former les enquêteurs sur le questionnaire.",
                "Prévoir un test pilote sur 5% de l'échantillon.",
            ],
        }

    def _default_sample(self, target: int) -> int:
        # Formule simplifiée : ~10% plafonné à 500
        return min(500, max(30, int(target * 0.1)))

    def _margin_of_error(self, n: int, N: int) -> float:
        # Marge d'erreur pour proportion 0.5, confiance 95%
        if n <= 0:
            return 1.0
        fpc = math.sqrt(max(0, (N - n) / (N - 1))) if N > 1 else 1.0
        return 1.96 * math.sqrt(0.25 / n) * fpc


class EchantillonneurAgent:
    """Calcule la taille d'échantillon optimale selon la marge d'erreur souhaitée."""

    code = "echantillonneur"
    name = "Agent Échantillonneur"

    def propose_sample_size(
        self,
        target_population: int,
        confidence_level: float = 0.95,
        margin_error: float = 0.05,
        proportion: float = 0.5,
    ) -> Dict[str, Any]:
        # z-score selon niveau de confiance
        z = self._z_score(confidence_level)

        # Taille d'échantillon initiale (population infinie)
        n0 = (z ** 2) * proportion * (1 - proportion) / (margin_error ** 2)

        # Correction pour population finie
        N = max(target_population, 1)
        n = n0 / (1 + (n0 - 1) / N)
        n_final = int(math.ceil(n))

        return {
            "target_population": N,
            "confidence_level": confidence_level,
            "margin_error": margin_error,
            "assumed_proportion": proportion,
            "calculated_sample_size": n_final,
            "formula": "n = (z² × p × (1-p) / e²) / (1 + (n0-1)/N)",
            "recommended_with_attrition": int(math.ceil(n_final * 1.1)),
            "rationale": (
                f"Pour une population de {N}, avec une confiance de "
                f"{int(confidence_level*100)}% et une marge d'erreur de "
                f"{int(margin_error*100)}%, il faut interroger {n_final} personnes "
                f"(prévoir {int(math.ceil(n_final*1.1))} avec 10% d'attrition)."
            ),
        }

    def _z_score(self, confidence: float) -> float:
        # Table z simplifiée
        table = {
            0.90: 1.645,
            0.95: 1.960,
            0.99: 2.576,
        }
        # Chercher la clé la plus proche
        closest = min(table.keys(), key=lambda k: abs(k - confidence))
        return table[closest]


# Instances réutilisables
methodologue_agent = MethodologueAgent()
echantillonneur_agent = EchantillonneurAgent()