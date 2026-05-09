from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
import re
from .utils import chatbot_ai

class ChatbotView(APIView):
    permission_classes = [IsAuthenticated]

    # Mots-clés interdits pour détecter les tentatives de diagnostic ou prescription
    FORBIDDEN_KEYWORDS = [
        r"diag", r"maladie", r"soigner", r"guérir", r"j'ai mal", r"douleur au", 
        r"ordonnance", r"prescription", r"docteur", r"examen", r"analyse",
        r"mridh", r"wji3a", r"tbib", r"dwa jdid", r"consultation"
    ]

    def post(self, request):
        message = request.data.get('message', '').strip()
        lang = request.data.get('lang', 'fr') # fr, en, tn

        if not message:
            return Response({'error': 'Message vide.'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Vérification automatique (Loi 91-21)
        for pattern in self.FORBIDDEN_KEYWORDS:
            if re.search(pattern, message.lower()):
                refusal = self.get_legal_refusal(lang)
                return Response({'response': refusal}, status=status.HTTP_200_OK)

        # 2. Génération IA via le modèle local
        try:
            # On mappe 'tn' vers 'fr' ou 'en' pour le modèle si besoin, 
            # mais Flan-T5 comprend le mélange. On demande de répondre dans la langue cible.
            model_lang = "French" if lang == 'fr' else "English" if lang == 'en' else "Tunisian Arabic/French"
            
            ai_response = chatbot_ai.generate_response(message, language=model_lang)
            return Response({'response': ai_response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f"Erreur IA: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_legal_refusal(self, lang):
        if lang == 'tn':
            return (
                "Sama7ni, manajamech na3tik diagnostic wala ordonnance. "
                "Hasb el kanoun tounsi n°91-21, lezem temchi l tbib. "
                "Najem n3awnek f ma3loumet 3la dwe déjà 3andek."
            )
        elif lang == 'en':
            return (
                "I apologize, but I cannot provide a medical diagnosis or prescription. "
                "According to Tunisian Law No. 91-21, you must consult a doctor for this. "
                "I can only help you with information about existing medications."
            )
        else:
            return (
                "Je m'excuse, mais je ne suis pas autorisé à fournir un diagnostic ou une prescription médicale. "
                "Conformément à la loi tunisienne n°91-21, vous devez consulter un médecin pour cela. "
                "Je peux toutefois vous renseigner sur la posologie ou les effets d'un médicament."
            )
