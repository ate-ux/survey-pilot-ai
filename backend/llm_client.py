"""Client LLM Groq pour SurveyPilot AI."""
import os
from typing import Optional
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

_client = None


def get_client():
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY manquante dans .env")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def is_available() -> bool:
    return bool(GROQ_API_KEY)


def ask_llm(
    prompt: str,
    system: str = "Tu es un assistant expert en méthodologie d'enquête et en analyse statistique. Tu réponds en français, de manière concise et professionnelle.",
    max_tokens: int = 800,
    temperature: float = 0.5,
) -> Optional[str]:
    """
    Envoie un prompt à Groq et retourne la réponse texte.
    """
    if not is_available():
        return None

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[llm_client] Erreur Groq: {e}")
        return None