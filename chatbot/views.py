# chatbot/views.py
"""
ChatbotView & PrescriptionScannerView
Architecture : System Prompt détaillé + contexte DB injecté dynamiquement.
Toute la logique de langage, refus légal et multilingue → system prompt.
Python → uniquement fetch DB et validation.
"""

from __future__ import annotations

import logging
import re

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .utils import chatbot_ai
from pharmacies.models import Pharmacie
from stock.models import Medicament, StockPharmacie

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  SYSTEM PROMPT — toute la logique de comportement est ici
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
Tu es **PharmBot**, un assistant pharmaceutique intelligent intégré à **TuniServe**,
une application pharmaceutique tunisienne.

═══════════════════════════════════════════════
 IDENTITÉ & COMPORTEMENT
═══════════════════════════════════════════════
- Tu réponds TOUJOURS dans la langue de l'utilisateur :
    • Français          → réponds en français
    • Anglais           → réponds en anglais
    • Arabe tunisien    → réponds en darija / franco-arabe
- Tu es professionnel, bienveillant, précis et concis (max 150 mots).
- Tu utilises des emojis avec modération : 💊 ✅ ❌ 📍 ⚠️

═══════════════════════════════════════════════
 CE QUE TU PEUX FAIRE ✅
═══════════════════════════════════════════════
1. Informer sur la posologie, effets secondaires, conservation et
   interactions d'un médicament (à titre informatif uniquement).
2. Donner le prix officiel d'un médicament (depuis le contexte).
3. Indiquer les pharmacies proches ayant le médicament en stock,
   avec distance et numéro de téléphone (depuis le contexte).
4. Répondre à des questions générales de santé et d'hygiène.
5. Expliquer comment utiliser ou conserver un médicament.
6. Informer sur les génériques disponibles.

═══════════════════════════════════════════════
 CE QUE TU NE DOIS JAMAIS FAIRE ❌
═══════════════════════════════════════════════
1. JAMAIS établir un diagnostic médical.
2. JAMAIS rédiger, suggérer ou valider une ordonnance.
3. JAMAIS recommander un médicament pour une maladie non diagnostiquée.
4. JAMAIS inventer des informations absentes du contexte (prix, stocks, distances).
5. JAMAIS remplacer l'avis d'un médecin ou d'un pharmacien.

═══════════════════════════════════════════════
 RÈGLE LÉGALE ABSOLUE — Loi tunisienne n°91-21
═══════════════════════════════════════════════
Si l'utilisateur demande un diagnostic, une prescription, ou des phrases comme
"j'ai mal à...", "je souffre de...", "quelle maladie j'ai", "quel médicament prendre
pour...", "prescris-moi...", tu DOIS répondre dans sa langue :

  🇫🇷 FR : "Je ne suis pas autorisé à fournir un diagnostic ou une prescription.
            Conformément à la loi tunisienne n°91-21, veuillez consulter un médecin.
            Je peux vous renseigner sur un médicament que vous avez déjà."

  🇬🇧 EN : "I'm not authorized to provide a medical diagnosis or prescription.
            Under Tunisian Law No. 91-21, please consult a licensed doctor.
            I can help with information about a medication you already have."

  🇹🇳 TN : "Sama7ni, manajamech na3tik diagnostic wala ordonnance.
            Hasb el kanoun tounsi n°91-21, lezem temchi l tbib.
            Najem n3awnek f ma3loumet 3la dwe déjà 3andek."

═══════════════════════════════════════════════
 CONTEXTE DONNÉES RÉELLES (base de données TuniServe)
═══════════════════════════════════════════════
Utilise IMPÉRATIVEMENT ces données pour répondre.
Ne mentionne jamais les détails techniques (noms de tables, IDs, etc.).
Si une information est absente, dis honnêtement : "Je n'ai pas cette information."

{context}

═══════════════════════════════════════════════
 FORMAT DE RÉPONSE
═══════════════════════════════════════════════
- Réponses courtes, structurées, max 150 mots.
- Termine TOUJOURS par : "⚕️ Consultez votre pharmacien pour plus de détails."
  (adapté dans la langue de l'utilisateur)
"""


# ═══════════════════════════════════════════════════════════════
#  HELPERS — uniquement fetch de données brutes
# ═══════════════════════════════════════════════════════════════

STOP_WORDS = {
    "pour", "dans", "avec", "plait", "prix", "coute", "combien",
    "cherche", "trouver", "quel", "quelle", "quels", "quelles",
    "cette", "avez", "vous", "nous", "tout", "tous", "salle",
    "jour", "nuit", "garde", "horaire", "plus", "proche", "ouvert",
    "ouverte", "ferme", "fermee", "maintenant", "distance", "bonjour",
    "merci", "svp", "stp", "bonsoir", "comment", "avec",
}


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value, default: int = 1) -> int:
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        return default


def _validate_image(image_file) -> str | None:
    """Valide type et taille. Retourne message d'erreur ou None."""
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_SIZE_MB = 5
    if image_file.content_type not in ALLOWED_TYPES:
        return "Format non supporté. Utilisez JPG, PNG ou WEBP."
    if image_file.size > MAX_SIZE_MB * 1024 * 1024:
        return f"Image trop lourde (max {MAX_SIZE_MB} Mo)."
    return None


def _build_pharmacies_context(lat: float, lng: float) -> str:
    """
    Récupère les pharmacies les plus proches avec annotation de distance SQL (Haversine).
    Évite de charger toutes les pharmacies en mémoire.
    """
    from django.db.models import ExpressionWrapper, FloatField, Value
    from django.db.models.functions import ACos, Cos, Sin, Radians

    now = timezone.localtime(timezone.now())

    try:
        pharmacies = (
            Pharmacie.objects
            .filter(est_active=True)
            .annotate(
                distance_km=ExpressionWrapper(
                    6371 * ACos(
                        Cos(Radians(Value(lat))) * Cos(Radians("latitude")) *
                        Cos(Radians("longitude") - Radians(Value(lng))) +
                        Sin(Radians(Value(lat))) * Sin(Radians("latitude"))
                    ),
                    output_field=FloatField(),
                )
            )
            .select_related("delegation")
            .order_by("distance_km")
            [:20]
        )
    except Exception as e:
        logger.error("[build_pharmacies_context] DB error: %s", e)
        return "Données pharmacies indisponibles."

    ouvertes, fermees = [], []
    for p in pharmacies:
        delegation = f" à {p.delegation.nom}" if p.delegation else ""
        tel        = p.telephone or "N/A"
        ligne = (
            f"  • {p.nom}{delegation} — "
            f"{p.distance_km:.2f} km — "
            f"Tél : {tel}"
        )
        if p.verifier_ouverture(now.date(), now.time()):
            ouvertes.append(ligne)
        else:
            fermees.append(ligne)

    lines = [f"📍 Position utilisateur : lat={lat}, lng={lng}\n"]
    lines.append("Pharmacies OUVERTES les plus proches :")
    lines += ouvertes[:5] or ["  Aucune pharmacie ouverte à proximité."]
    lines.append("\nPharmacies FERMÉES les plus proches :")
    lines += fermees[:5] or ["  Aucune pharmacie fermée à proximité."]

    return "\n".join(lines)


def _build_medications_context(message: str, lat: float | None, lng: float | None) -> str:
    """
    Extrait les mots significatifs du message, cherche les médicaments
    correspondants en DB (une seule requête via Prefetch) et retourne
    le contexte textuel pour le system prompt.
    """
    words = [
        w for w in re.findall(r"\b\w{4,}\b", message, re.UNICODE)
        if w.lower() not in STOP_WORDS
    ]

    if not words:
        return ""

    query_filter = Q()
    for word in words:
        query_filter |= Q(nom__icontains=word) | Q(dci__icontains=word)

    stocks_prefetch = Prefetch(
        "stocks",
        queryset=(
            StockPharmacie.objects
            .filter(quantite_stock__gt=0)
            .select_related("pharmacie", "pharmacie__delegation")
        ),
        to_attr="stocks_dispos",
    )

    matched_meds = (
        Medicament.objects
        .filter(query_filter)
        .select_related("categorie")
        .prefetch_related(stocks_prefetch)
        [:5]
    )

    if not matched_meds:
        return ""

    lines = ["💊 Médicaments trouvés dans la base de données :"]

    for med in matched_meds:
        stocks: list = med.stocks_dispos
        total_stocks  = len(stocks)

        pharmacies_info = []
        for s in stocks[:10]:
            delegation = f" à {s.pharmacie.delegation.nom}" if s.pharmacie.delegation else ""
            dist_str   = ""
            if lat is not None and lng is not None:
                try:
                    dist     = s.pharmacie.distance_km(lat, lng)
                    dist_str = f" ({dist:.2f} km)"
                except Exception:
                    pass
            pharmacies_info.append(f"{s.pharmacie.nom}{delegation}{dist_str}")

        if total_stocks == 0:
            disponibilite = "❌ En rupture de stock partout"
        elif total_stocks > 10:
            disponibilite = ", ".join(pharmacies_info) + f" et {total_stocks - 10} autres"
        else:
            disponibilite = ", ".join(pharmacies_info)

        lines.append(
            f"\n  Nom            : {med.nom}\n"
            f"  DCI            : {med.dci or 'Non spécifié'}\n"
            f"  Catégorie      : {med.categorie.nom if med.categorie else 'N/A'}\n"
            f"  Prix officiel  : {med.prix_vente:.3f} DT\n"
            f"  Ordonnance     : {'Oui ⚠️' if med.ordonnance_requise else 'Non'}\n"
            f"  Disponible à   : {disponibilite}"
        )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  VUE CHATBOT
# ═══════════════════════════════════════════════════════════════

class ChatbotView(APIView):
    """
    Chatbot pharmaceutique.
    Python → validation + fetch DB.
    IA (via system prompt) → langage, refus légal, format, multilingue.
    """

    permission_classes = [IsAuthenticated]
    VALID_LANGS        = {"fr", "en", "tn"}

    def post(self, request) -> Response:
        message = request.data.get("message", "").strip()
        lang    = request.data.get("lang", "fr")
        lat     = _safe_float(request.data.get("lat"))
        lng     = _safe_float(request.data.get("lng"))

        if not message:
            return Response(
                {"error": "Message vide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if lang not in self.VALID_LANGS:
            lang = "fr"

        # Construction du contexte DB (données brutes uniquement)
        context_parts = []

        if lat is not None and lng is not None:
            context_parts.append(_build_pharmacies_context(lat, lng))

        med_context = _build_medications_context(message, lat, lng)
        if med_context:
            context_parts.append(med_context)

        context_str = "\n\n".join(context_parts) if context_parts else "Aucun contexte disponible."

        # Génération IA — le system prompt gère tout le reste
        try:
            ai_response = chatbot_ai.generate_response(
                message=message,
                system_prompt=SYSTEM_PROMPT.format(context=context_str),
            )
            return Response({"response": ai_response}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("[ChatbotView] IA error: %s", e)
            return Response(
                {"error": "Service IA temporairement indisponible."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ═══════════════════════════════════════════════════════════════
#  VUE SCANNER D'ORDONNANCE
# ═══════════════════════════════════════════════════════════════

class PrescriptionScannerView(APIView):
    """
    Analyse une image d'ordonnance via Groq Vision,
    puis enrichit les résultats avec prix et stocks depuis la DB.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        if "image" not in request.FILES:
            return Response(
                {"error": "Aucune image fournie."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        image_file = request.FILES["image"]

        # Validation image
        error = _validate_image(image_file)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        # Analyse IA
        extracted_meds = chatbot_ai.analyze_prescription(image_file)

        if not extracted_meds:
            return Response(
                {
                    "response": (
                        "Désolé, je n'ai pas pu lire les médicaments sur cette image. "
                        "Assurez-vous que l'image est nette et bien éclairée."
                    )
                },
                status=status.HTTP_200_OK,
            )

        # Enrichissement DB + formatage
        results, total_sum = self._enrich_with_db(extracted_meds)
        response_text      = self._format_response(results, total_sum)

        return Response(
            {
                "response":    response_text,
                "medications": results,
                "total":       round(total_sum, 3),
            },
            status=status.HTTP_200_OK,
        )

    # ── Helpers privés ──────────────────────────────────────────

    @staticmethod
    def _enrich_with_db(extracted_meds: list[dict]) -> tuple[list[dict], float]:
        """
        Recherche chaque médicament en DB et récupère prix + disponibilité.
        Retourne (results, total_sum).
        """
        results:   list[dict] = []
        total_sum: float      = 0.0

        for item in extracted_meds:
            nom      = str(item.get("nom", "")).strip()
            quantite = _safe_int(item.get("quantite", 1))

            if not nom:
                continue

            # Recherche flexible : nom complet → premier mot
            base_nom = nom.split()[0]
            med = (
                Medicament.objects
                .filter(Q(nom__icontains=nom) | Q(dci__icontains=nom))
                .first()
            ) or (
                Medicament.objects
                .filter(Q(nom__icontains=base_nom) | Q(dci__icontains=base_nom))
                .first()
            )

            if med:
                prix       = float(med.prix_vente)
                sous_total = round(prix * quantite, 3)
                total_sum += sous_total

                # ✅ stocks dans une variable locale propre (corrige le NameError)
                stocks_qs     = StockPharmacie.objects.filter(
                    medicament=med, quantite_stock__gt=0
                ).select_related("pharmacie")

                total_stocks      = stocks_qs.count()
                pharmacies_dispos = [s.pharmacie.nom for s in stocks_qs[:3]]

                results.append({
                    "nom_original":     nom,
                    "nom_bdd":          med.nom,
                    "quantite":         quantite,
                    "prix_unitaire":    prix,
                    "sous_total":       sous_total,
                    "trouve":           True,
                    "total_stocks":     total_stocks,
                    "pharmacies_dispos": pharmacies_dispos,
                })
            else:
                results.append({
                    "nom_original": nom,
                    "quantite":     quantite,
                    "trouve":       False,
                })

        return results, round(total_sum, 3)

    @staticmethod
    def _format_response(results: list[dict], total_sum: float) -> str:
        """Formate les résultats en texte lisible."""
        lines = ["Voici l'analyse de votre ordonnance :\n"]

        for res in results:
            if res["trouve"]:
                lines.append(
                    f"💊 **{res['nom_bdd']}** (x{res['quantite']}) "
                    f": {res['sous_total']:.3f} DT"
                )
                pharmacies  = res["pharmacies_dispos"]
                total       = res["total_stocks"]

                if pharmacies:
                    suffix = "..." if total > 3 else ""
                    lines.append(f"   ✅ Disponible à : {', '.join(pharmacies)}{suffix}")
                else:
                    lines.append("   ❌ En rupture de stock partout")
            else:
                lines.append(
                    f"💊 **{res['nom_original']}** (x{res['quantite']}) "
                    f": Non reconnu dans la base"
                )

        lines.append(f"\n💰 **Somme totale estimée : {total_sum:.3f} DT**")
        lines.append("\n*Note : Ces prix et stocks sont indicatifs et peuvent varier.*")

        return "\n".join(lines)