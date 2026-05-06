from django.utils import timezone
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

DELAI_ANTI_DOUBLON_HEURES = 24


# ── Messages ───────────────────────────────────────────────────────────────────

def _msg_stock_faible(medicament_nom, quantite_stock, seuil_alerte, pharmacie_nom) -> str:
    return (
        f"Alerte stock faible !\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Médicament : {medicament_nom}\n"
        f"Stock      : {quantite_stock} unités\n"
        f"Seuil      : {seuil_alerte} unités\n"
        f"Pensez à réapprovisionner."
    )


def _msg_rupture_stock(medicament_nom, pharmacie_nom) -> str:
    return (
        f"RUPTURE DE STOCK !\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Médicament : {medicament_nom}\n"
        f"Réapprovisionnement urgent nécessaire."
    )


def _msg_expiration_proche(medicament_nom, date_expiration, pharmacie_nom) -> str:
    date_str = date_expiration.strftime('%d/%m/%Y')
    return (
        f"Médicament expire bientôt !\n"
        f"Pharmacie  : {pharmacie_nom}\n"
        f"Médicament : {medicament_nom}\n"
        f"Expire le  : {date_str}\n"
        f"Pensez à le retirer de la vente."
    )


# ── Anti-doublon ───────────────────────────────────────────────────────────────

def _notification_recente_existe(pharmacie, medicament, type_notif: str) -> bool:
    from .models import Notification
    seuil = timezone.now() - timedelta(hours=DELAI_ANTI_DOUBLON_HEURES)
    return Notification.objects.filter(
        pharmacie=pharmacie,
        medicament=medicament,
        type=type_notif,
        statut='envoye',
        created_at__gte=seuil,
    ).exists()


# ── Logique de notification ────────────────────────────────────────────────────

def verifier_et_notifier_stock(stock) -> None:
    from .models import Notification
    from messagerie.utils import envoyer_notification_ws

    try:
        pharmacien = stock.pharmacie.proprietaire
        if not pharmacien:
            return

        pharmacie_nom  = stock.pharmacie.nom
        medicament_nom = stock.medicament.nom

        if stock.en_rupture:
            type_notif = 'rupture_stock'
            titre      = 'Rupture de stock'
            msg        = _msg_rupture_stock(medicament_nom, pharmacie_nom)
        elif stock.stock_faible:
            type_notif = 'stock_faible'
            titre      = 'Stock faible'
            msg        = _msg_stock_faible(medicament_nom, stock.quantite_stock,
                                           stock.seuil_alerte, pharmacie_nom)
        else:
            return

        if _notification_recente_existe(stock.pharmacie, stock.medicament, type_notif):
            logger.info(f"Notification '{type_notif}' déjà envoyée récemment pour "
                        f"{medicament_nom} ({pharmacie_nom}). Ignorée.")
            return

        ok = envoyer_notification_ws(pharmacien.pk, type_notif, titre, msg)

        Notification.objects.create(
            pharmacie=stock.pharmacie,
            medicament=stock.medicament,
            type=type_notif,
            message=msg,
            statut='envoye' if ok else 'echec',
            destinataire=pharmacien.email,
        )

    except Exception as e:
        logger.error(f"Erreur notification stock (stock_id={stock.pk}) : {e}")


def verifier_et_notifier_stock_virtuel(stock, quantite_virtuelle: int) -> None:
    from .models import Notification
    from messagerie.utils import envoyer_notification_ws

    try:
        pharmacien = stock.pharmacie.proprietaire
        if not pharmacien:
            return

        pharmacie_nom  = stock.pharmacie.nom
        medicament_nom = stock.medicament.nom

        if quantite_virtuelle <= 0:
            type_notif = 'rupture_stock'
            titre      = 'Rupture de stock'
            msg        = _msg_rupture_stock(medicament_nom, pharmacie_nom)
        elif quantite_virtuelle <= stock.seuil_alerte:
            type_notif = 'stock_faible'
            titre      = 'Stock faible'
            msg        = _msg_stock_faible(medicament_nom, quantite_virtuelle,
                                           stock.seuil_alerte, pharmacie_nom)
        else:
            return

        if _notification_recente_existe(stock.pharmacie, stock.medicament, type_notif):
            logger.info(f"Notification '{type_notif}' déjà envoyée récemment. Ignorée.")
            return

        ok = envoyer_notification_ws(pharmacien.pk, type_notif, titre, msg)

        Notification.objects.create(
            pharmacie=stock.pharmacie,
            medicament=stock.medicament,
            type=type_notif,
            message=msg,
            statut='envoye' if ok else 'echec',
            destinataire=pharmacien.email,
        )

    except Exception as e:
        logger.error(f"Erreur notification stock virtuel (stock_id={stock.pk}) : {e}")


def notifier_expirations_proches(jours: int = 30) -> int:
    from datetime import date, timedelta as td
    from .models import StockPharmacie, Notification
    from messagerie.utils import envoyer_notification_ws

    date_limite = date.today() + td(days=jours)
    stocks = (
        StockPharmacie.objects
        .select_related('pharmacie__proprietaire', 'medicament')
        .filter(medicament__date_expiration__lte=date_limite, quantite_stock__gt=0)
    )

    total_envoyes = 0

    for stock in stocks:
        try:
            pharmacien = stock.pharmacie.proprietaire
            if not pharmacien:
                logger.warning(f"Pas de propriétaire pour la pharmacie {stock.pharmacie.nom}")
                continue

            if _notification_recente_existe(stock.pharmacie, stock.medicament, 'expiration'):
                logger.info(f"Notification 'expiration' déjà envoyée pour "
                            f"{stock.medicament.nom} ({stock.pharmacie.nom}). Ignorée.")
                continue

            msg = _msg_expiration_proche(
                medicament_nom=stock.medicament.nom,
                date_expiration=stock.medicament.date_expiration,
                pharmacie_nom=stock.pharmacie.nom,
            )

            ok = envoyer_notification_ws(pharmacien.pk, 'expiration', 'Expiration proche', msg)

            Notification.objects.create(
                pharmacie=stock.pharmacie,
                medicament=stock.medicament,
                type='expiration',
                message=msg,
                statut='envoye' if ok else 'echec',
                destinataire=pharmacien.email,
            )

            if ok:
                total_envoyes += 1

        except Exception as e:
            logger.error(f"Erreur notification expiration (stock_id={stock.pk}) : {e}")

    return total_envoyes
