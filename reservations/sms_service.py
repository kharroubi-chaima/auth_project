from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)


def envoyer_sms(destinataire: str, message: str) -> bool:
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_FROM_NUMBER,
            to=destinataire,
        )
        logger.info(f"SMS envoye a {destinataire}")
        return True
    except Exception as e:
        logger.error(f"Erreur SMS vers {destinataire} : {e}")
        return False


# ── SMS Citoyen — Confirmation ────────────────────────────────────────────────
def sms_reservation_confirmee(
    pharmacie_nom: str,
    medicament_nom: str,
    quantite: int,
    expire_at,
    citoyen_prenom: str = '',
) -> str:
    heure = expire_at.strftime('%H:%M')
    prenom = f" {citoyen_prenom}" if citoyen_prenom else ''
    return (
        f"Bonjour{prenom} !\n"
        f"Votre reservation TuniService est confirmee.\n"
        f"---\n"
        f"Medicament : {medicament_nom} x{quantite}\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Expire a   : {heure}\n"
        f"---\n"
        f"Presentez ce message a la pharmacie."
    )


# ── SMS Citoyen — Annulation ──────────────────────────────────────────────────
def sms_reservation_annulee(
    medicament_nom: str,
    pharmacie_nom: str,
    citoyen_prenom: str = '',
) -> str:
    prenom = f" {citoyen_prenom}" if citoyen_prenom else ''
    return (
        f"Bonjour{prenom},\n"
        f"Votre reservation a ete annulee.\n"
        f"---\n"
        f"Medicament : {medicament_nom}\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"---\n"
        f"Vous pouvez faire une nouvelle recherche sur TuniService."
    )


# ── SMS Citoyen — Récupération confirmée ─────────────────────────────────────
def sms_reservation_recuperee(
    medicament_nom: str,
    quantite: int,
    pharmacie_nom: str = '',
    citoyen_prenom: str = '',
) -> str:
    prenom = f" {citoyen_prenom}" if citoyen_prenom else ''
    pharmacie = f"\nPharmacie  : {pharmacie_nom}" if pharmacie_nom else ''
    return (
        f"Bonjour{prenom} !\n"
        f"Votre medicament a bien ete recupere.\n"
        f"---\n"
        f"Medicament : {medicament_nom} x{quantite}"
        f"{pharmacie}\n"
        f"---\n"
        f"Merci de votre confiance. A bientot sur TuniService !"
    )


# ── SMS Pharmacien — Nouvelle réservation ─────────────────────────────────────
def sms_nouvelle_reservation_pharmacien(
    citoyen_nom: str,
    medicament_nom: str,
    quantite: int,
    pharmacie_nom: str,
    expire_at,
) -> str:
    heure = expire_at.strftime('%H:%M')
    return (
        f"[TuniService] Nouvelle reservation !\n"
        f"---\n"
        f"Citoyen    : {citoyen_nom}\n"
        f"Medicament : {medicament_nom} x{quantite}\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Valable jusqu'a : {heure}\n"
        f"---\n"
        f"Connectez-vous sur TuniService pour confirmer."
    )