import logging
from messagerie.utils import envoyer_notification_ws

logger = logging.getLogger(__name__)


def notifier_reservation_confirmee(
    citoyen_id: int,
    pharmacie_nom: str,
    medicament_nom: str,
    quantite: int,
    expire_at,
    citoyen_prenom: str = '',
) -> bool:
    heure  = expire_at.strftime('%H:%M')
    prenom = f" {citoyen_prenom}" if citoyen_prenom else ''
    message = (
        f"Bonjour{prenom} !\n"
        f"Votre réservation TuniService est confirmée.\n"
        f"Médicament : {medicament_nom} x{quantite}\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Expire à   : {heure}\n"
        f"Présentez cette notification à la pharmacie."
    )
    return envoyer_notification_ws(citoyen_id, 'reservation_confirmee', 'Réservation confirmée', message)


def notifier_reservation_annulee(
    citoyen_id: int,
    medicament_nom: str,
    pharmacie_nom: str,
    citoyen_prenom: str = '',
) -> bool:
    prenom = f" {citoyen_prenom}" if citoyen_prenom else ''
    message = (
        f"Bonjour{prenom},\n"
        f"Votre réservation a été annulée.\n"
        f"Médicament : {medicament_nom}\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Vous pouvez faire une nouvelle recherche sur TuniService."
    )
    return envoyer_notification_ws(citoyen_id, 'reservation_annulee', 'Réservation annulée', message)


def notifier_reservation_expiree(
    citoyen_id: int,
    medicament_nom: str,
    pharmacie_nom: str,
    citoyen_prenom: str = '',
) -> bool:
    prenom = f" {citoyen_prenom}" if citoyen_prenom else ''
    message = (
        f"Bonjour{prenom},\n"
        f"Votre réservation a expiré.\n"
        f"Médicament : {medicament_nom}\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Le stock a été libéré."
    )
    return envoyer_notification_ws(citoyen_id, 'reservation_expiree', 'Réservation expirée', message)


def notifier_reservation_recuperee(
    citoyen_id: int,
    medicament_nom: str,
    quantite: int,
    pharmacie_nom: str = '',
    citoyen_prenom: str = '',
) -> bool:
    prenom    = f" {citoyen_prenom}" if citoyen_prenom else ''
    pharmacie = f"\nPharmacie  : {pharmacie_nom}" if pharmacie_nom else ''
    message = (
        f"Bonjour{prenom} !\n"
        f"Votre médicament a bien été récupéré.\n"
        f"Médicament : {medicament_nom} x{quantite}{pharmacie}\n"
        f"Merci de votre confiance. À bientôt sur TuniService !"
    )
    return envoyer_notification_ws(citoyen_id, 'reservation_recuperee', 'Médicament récupéré', message)


def notifier_nouvelle_reservation_pharmacien(
    pharmacien_id: int,
    citoyen_nom: str,
    medicament_nom: str,
    quantite: int,
    pharmacie_nom: str,
    expire_at,
) -> bool:
    heure   = expire_at.strftime('%H:%M')
    message = (
        f"Nouvelle réservation !\n"
        f"Citoyen    : {citoyen_nom}\n"
        f"Médicament : {medicament_nom} x{quantite}\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Valable jusqu'à : {heure}\n"
        f"Connectez-vous sur TuniService pour confirmer."
    )
    return envoyer_notification_ws(pharmacien_id, 'nouvelle_reservation', 'Nouvelle réservation', message)
