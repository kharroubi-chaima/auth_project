# chatbot/utils.py
"""
ChatbotAI — Wrapper Groq pour PharmBot.
Toute la logique de langage, de refus légal et de comportement
est dans le system prompt de views.py (injecté via generate_response).
Ce fichier ne fait que communiquer avec l'API Groq.
"""

import base64
import json
import logging
import os

from groq import Groq

logger = logging.getLogger(__name__)


class ChatbotAI:
    """
    Singleton — une seule instance Groq partagée.
    Deux responsabilités uniquement :
      1. generate_response() → chat texte
      2. analyze_prescription() → vision ordonnance
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Évite la ré-initialisation à chaque appel du singleton
        if self._initialized:
            return
        self._initialized = True

        # ✅ Clé API depuis variable d'environnement (avec fallback vide)
        api_key = os.environ.get("GROQ_API_KEY", "")

        self.client     = Groq(api_key=api_key)
        self.model_chat = "llama-3.3-70b-versatile"
        self.model_vision = "meta-llama/llama-4-scout-17b-16e-instruct"

    # ─────────────────────────────────────────────
    # CHAT
    # ─────────────────────────────────────────────

    def generate_response(self, message: str, system_prompt: str) -> str:
        """
        Génère une réponse via Groq.

        Le system_prompt complet (avec contexte DB déjà injecté)
        est passé depuis views.py — cette méthode ne contient
        aucune logique métier.

        Args:
            message:       Message de l'utilisateur.
            system_prompt: System prompt complet avec contexte.

        Returns:
            Réponse textuelle de l'IA.
        """
        if not message or not message.strip():
            return "Bonjour ! Posez-moi une question sur un médicament."

        try:
            response = self.client.chat.completions.create(
                model=self.model_chat,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": message},
                ],
                max_tokens=400,
                temperature=0.3,   # Légèrement créatif mais reste factuel
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error("[ChatbotAI] generate_response error: %s", e)
            # Message d'erreur générique — la langue est gérée côté view si besoin
            return (
                "Service temporairement indisponible. "
                "Veuillez consulter votre pharmacien directement."
            )

    # ─────────────────────────────────────────────
    # VISION — SCAN ORDONNANCE
    # ─────────────────────────────────────────────

    def analyze_prescription(self, image_file) -> list[dict]:
        """
        Analyse une image d'ordonnance via Groq Vision.

        Args:
            image_file: Fichier image Django (InMemoryUploadedFile).

        Returns:
            Liste de dicts [{"nom": str, "quantite": int}, ...]
            ou [] si aucun médicament détecté / erreur.
        """
        VISION_PROMPT = """
You are a pharmacist assistant specialized in reading medical prescriptions.

Your task:
1. Identify ALL medication names exactly as written on the prescription.
2. Extract or calculate the total quantity of doses/injections/boxes needed for the entire duration of the prescription. 
   - If a treatment schedule is specified (e.g., "1 injection at S0, then 1 injection at S2, then 1 injection at S6, then 1 injection every 2 months for 6 months"), you MUST calculate the sum of all injections requested.
   - Induction phase: S0 (1), S2 (1), S6 (1) = 3 injections.
   - Maintenance phase: 1 injection every 2 months for a duration of 6 months = 6 / 2 = 3 injections.
   - Total for this prescription = 3 + 3 = 6 injections.
   - Do this exact mathematical summation for any scheduled treatment.
3. If handwritten, use your medical knowledge to decipher the text.

Output rules:
- Return ONLY a valid JSON object — no markdown, no explanation, no extra text.
- Format: {"medications": [{"nom": "MedicamentName", "quantite": 6}]}
- If nothing found or image unreadable: {"medications": []}
"""
        try:
            # Encodage base64 de l'image
            image_bytes  = image_file.read()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Détecter le type MIME réel
            content_type = getattr(image_file, "content_type", "image/jpeg")

            response = self.client.chat.completions.create(
                model=self.model_vision,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VISION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1000,
                temperature=0.0,  # Déterministe pour l'extraction de données
            )

            content = response.choices[0].message.content
            logger.debug("[ChatbotAI Vision] raw response: %s", content)

            return self._parse_medications_json(content)

        except Exception as e:
            logger.error("[ChatbotAI Vision] analyze_prescription error: %s", e)
            return []

    # ─────────────────────────────────────────────
    # HELPERS PRIVÉS
    # ─────────────────────────────────────────────

    @staticmethod
    def _parse_medications_json(content: str) -> list[dict]:
        """
        Extrait la liste de médicaments depuis la réponse brute de l'IA.
        Robuste aux backticks Markdown résiduels et aux espaces parasites.
        """
        # Nettoyage des balises Markdown éventuelles
        clean = content.replace("```json", "").replace("```", "").strip()

        # Extraction de l'objet JSON
        start = clean.find("{")
        end   = clean.rfind("}") + 1

        if start == -1 or end == 0:
            logger.warning("[ChatbotAI Vision] No JSON found in: %s", clean)
            return []

        json_str = clean[start:end]
        try:
            data = json.loads(json_str)
            medications = data.get("medications", [])

            # Validation légère de chaque entrée
            result = []
            for item in medications:
                nom = str(item.get("nom", "")).strip()
                if not nom:
                    continue
                try:
                    quantite = max(1, int(item.get("quantite", 1)))
                except (ValueError, TypeError):
                    quantite = 1
                result.append({"nom": nom, "quantite": quantite})

            return result

        except json.JSONDecodeError as e:
            logger.error("[ChatbotAI Vision] JSON parse error: %s | raw: %s", e, json_str)
            return []


# Instance singleton globale
chatbot_ai = ChatbotAI()