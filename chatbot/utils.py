# chatbot/utils.py
import re
from groq import Groq

class ChatbotAI:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.client = Groq(api_key="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")
        self.model  = "llama-3.3-70b-versatile"

        self.system_prompt = """
        Tu es un assistant pharmacie intelligent intégré dans TuniServe,
        une application pharmaceutique tunisienne.
        RÈGLES STRICTES (Loi tunisienne 91-21) :
        - Tu réponds UNIQUEMENT sur : posologie, effets secondaires,
          conservation, interactions, génériques, disponibilité
        - Tu ne fais JAMAIS de diagnostic médical
        - Tu ne prescris JAMAIS de traitement
        - Tu recommandes TOUJOURS de consulter un pharmacien ou médecin
        LANGUE : Tu détectes automatiquement la langue et réponds dans la même langue.
        CONTEXTE TUNISIEN : Tu connais les médicaments tunisiens (SIPHAT, ADWYA, UNIMED).
        FORMAT : Réponses courtes max 150 mots, terminer par recommandation de consulter.
        """

    def detect_language(self, text):
        text_lower = text.lower()
        if re.search(r'[\u0600-\u06FF]', text) or any(
            w in text_lower for w in ['kifeh','chnowa','mta3','aslema','wji3','dwa','barcha']
        ):
            return 'tn'
        if any(w in text_lower for w in ['how','what','dosage','side effects','medicine','tablet']):
            return 'en'
        return 'fr'

    def is_forbidden(self, text):
        forbidden = ["j'ai mal", 'je souffre', 'suis-je malade', 'prescrire', 'ordonnez-moi']
        return any(w in text.lower() for w in forbidden)

    def generate_response(self, user_message, language='fr'):
        if not user_message or not user_message.strip():
            return "Bonjour ! Posez-moi une question sur un médicament."

        lang = self.detect_language(user_message)

        if self.is_forbidden(user_message):
            return {
                'fr': "⚠️ Je ne peux pas établir de diagnostic. Consultez un médecin.",
                'tn': "⚠️ Ma najem4 na3mel diagnostic. Mchi 3and tbibek.",
                'en': "⚠️ I cannot make diagnoses. Please see a doctor."
            }[lang]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=300,
            )

            disclaimer = {
                'fr': "\n\n⚕️ Information indicative — Consultez votre pharmacien.",
                'tn': "\n\n⚕️ Ma3loumet indicative — Mchi 3and el pharmacien.",
                'en': "\n\n⚕️ Indicative information — Consult your pharmacist."
            }[lang]

            return response.choices[0].message.content + disclaimer

        except Exception as e:
            print(f"[ChatbotAI ERROR] {e}")
            return {
                'fr': "Service temporairement indisponible. Consultez votre pharmacien.",
                'tn': "Service mawjouch tawa. Mchi 3and el pharmacien.",
                'en': "Service temporarily unavailable. Please consult your pharmacist."
            }[lang]

chatbot_ai = ChatbotAI()