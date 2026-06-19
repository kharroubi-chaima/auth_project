# pharmacies/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from datetime import date, timedelta, time


@receiver(pre_save, sender='pharmacies.Pharmacie')
def track_pharmacie_changes(sender, instance, **kwargs):
    """
    Suit les changements d'état de la pharmacie pour savoir s'il faut
    déclencher une ré-génération globale des gardes de sa délégation.
    """
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._old_est_active = old.est_active
        instance._old_delegation_id = old.delegation_id
        instance._old_categorie = old.categorie
    except sender.DoesNotExist:
        instance._old_est_active = None
        instance._old_delegation_id = None
        instance._old_categorie = None


@receiver(post_save, sender='pharmacies.Pharmacie')
def generer_donnees_pharmacie(sender, instance, created, **kwargs):
    print(f" Signal déclenché ! created={created}, pharmacie={instance.nom}")

    from .models import GardePharmacie, HoraireRamadan, PeriodeRamadan, HoraireTravail, Pharmacie as P

    # 1. Si la pharmacie est inactive, on supprime ses gardes futures
    if not instance.est_active:
        GardePharmacie.objects.filter(pharmacie=instance, date_debut__gte=date.today()).delete()
        print(f" Pharmacie inactive, gardes futures supprimées.")
        
        # Si elle vient d'être désactivée, on doit réorganiser le planning des autres pour boucher les trous
        if getattr(instance, '_old_est_active', None) is True:
            pass # On laisse continuer pour déclencher la ré-génération (Partie B)
        else:
            return

    # 2. Vérifier s'il y a un changement structurel qui nécessite une ré-génération des gardes
    old_active = getattr(instance, '_old_est_active', None)
    old_delegation_id = getattr(instance, '_old_delegation_id', None)
    old_categorie = getattr(instance, '_old_categorie', None)

    should_generate = (
        created or
        old_active is False or
        (old_active is True and not instance.est_active) or # Ajout du cas de désactivation
        old_delegation_id != instance.delegation_id or
        old_categorie != instance.categorie
    )

    # ── A. Génération des horaires de base (toujours exécutée si manquante) ──
    # Horaires de travail
    HORAIRES_A = {
        0: (time(8, 30), time(19, 30), time(13, 0), time(15, 0)),  # Lundi
        1: (time(8, 30), time(19, 30), time(13, 0), time(15, 0)),  # Mardi
        2: (time(8, 30), time(19, 30), time(13, 0), time(15, 0)),  # Mercredi
        3: (time(8, 30), time(19, 30), time(13, 0), time(15, 0)),  # Jeudi
        4: (time(8, 30), time(19, 30), time(13, 0), time(15, 0)),  # Vendredi
        5: (time(8, 30), time(13, 0),  None,         None        ), # Samedi
        6: (None,        None,         None,         None        ), # Dimanche fermé
    }
    HORAIRES_B = {
        0: (time(19, 30), time(8, 30), None, None),  # Lundi
        1: (time(19, 30), time(8, 30), None, None),  # Mardi
        2: (time(19, 30), time(8, 30), None, None),  # Mercredi
        3: (time(19, 30), time(8, 30), None, None),  # Jeudi
        4: (time(19, 30), time(8, 30), None, None),  # Vendredi
        5: (time(19, 30), time(8, 30), None, None),  # Samedi
        6: (time(19, 30), time(8, 30), None, None),  # Dimanche
    }

    horaires = HORAIRES_A if instance.categorie == 'A' else HORAIRES_B
    for jour, (ouv, ferm, pause_d, pause_f) in horaires.items():
        HoraireTravail.objects.get_or_create(
            pharmacie=instance,
            jour=jour,
            defaults={
                'est_ouvert':      ouv is not None,
                'heure_ouverture': ouv,
                'heure_fermeture': ferm,
                'pause_debut':     pause_d,
                'pause_fin':       pause_f,
            }
        )

    # Horaires Ramadan (seulement cat A)
    if instance.categorie == 'A':
        periode = PeriodeRamadan.objects.filter(
            date_debut__lte=date.today(),
            date_fin__gte=date.today()
        ).first()

        if periode:
            HORAIRES_RAMADAN = {
                0: (time(8, 30), time(17, 0), None, None),  # Lundi
                1: (time(8, 30), time(17, 0), None, None),  # Mardi
                2: (time(8, 30), time(17, 0), None, None),  # Mercredi
                3: (time(8, 30), time(17, 0), None, None),  # Jeudi
                4: (time(8, 30), time(17, 0), None, None),  # Vendredi
                5: (time(8, 30), time(13, 0), None, None),  # Samedi
                6: (None,        None,        None, None),  # Dimanche fermé
            }
            for jour, (h1d, h1f, h2d, h2f) in HORAIRES_RAMADAN.items():
                HoraireRamadan.objects.get_or_create(
                    pharmacie=instance,
                    jour=jour,
                    defaults={
                        'est_ouvert':        h1d is not None,
                        'heure_ouverture_1': h1d,
                        'heure_fermeture_1': h1f,
                        'heure_ouverture_2': h2d,
                        'heure_fermeture_2': h2f,
                    }
                )

    if not should_generate:
        print(" Aucun changement structurel (activité, catégorie, délégation). Pas de ré-génération globale des gardes.")
        return

    # ── B. Ré-génération globale équitable des gardes de la délégation ──
    aujourd_hui = date.today()
    # Calcul de la fin du mois dans 4 mois (mois actuel + 3)
    target_month = aujourd_hui.month + 3
    target_year = aujourd_hui.year
    if target_month > 12:
        target_month -= 12
        target_year += 1
        
    if target_month == 12:
        fin_mois = date(target_year + 1, 1, 1) - timedelta(days=1)
    else:
        fin_mois = date(target_year, target_month + 1, 1) - timedelta(days=1)

    # 1. Supprimer et ré-générer les gardes pour la délégation/catégorie cible
    GardePharmacie.objects.filter(
        pharmacie__delegation=instance.delegation,
        pharmacie__categorie=instance.categorie,
        date_debut__gte=aujourd_hui,
        date_debut__lte=fin_mois
    ).delete()

    pharmacies_actives = list(P.objects.filter(
        delegation=instance.delegation,
        categorie=instance.categorie,
        est_active=True
    ).order_by('created_at', 'id'))

    if pharmacies_actives:
        jour_courant = aujourd_hui
        index = 0
        gardes_creees = 0

        while jour_courant <= fin_mois:
            jour_semaine = jour_courant.weekday()

            # Cat B : Garde de nuit toutes les nuits pour TOUTES les pharmacies
            if instance.categorie == 'B':
                for pharmacie in pharmacies_actives:
                    GardePharmacie.objects.create(
                        pharmacie=pharmacie,
                        date_debut=jour_courant,
                        date_fin=jour_courant,
                        type_garde='nuit'
                    )
                    gardes_creees += 1

            # Cat A : Garde de dimanche uniquement
            elif instance.categorie == 'A' and jour_semaine == 6:
                pharmacie = pharmacies_actives[index % len(pharmacies_actives)]
                GardePharmacie.objects.create(
                    pharmacie=pharmacie,
                    date_debut=jour_courant,
                    date_fin=jour_courant,
                    type_garde='dimanche'
                )
                gardes_creees += 1
                index += 1

            jour_courant += timedelta(days=1)

        print(f" [SUCCÈS] Ré-génération globale : {gardes_creees} gardes créées pour la délégation {instance.delegation.nom} (Cat. {instance.categorie})")

    # 2. Si l'ancienne délégation ou catégorie a changé, ré-générer aussi l'ancien groupe pour ré-équilibrer
    if old_delegation_id and old_categorie and (old_delegation_id != instance.delegation_id or old_categorie != instance.categorie):
        from localisations.models import Delegation
        try:
            old_delegation = Delegation.objects.get(pk=old_delegation_id)
            GardePharmacie.objects.filter(
                pharmacie__delegation=old_delegation,
                pharmacie__categorie=old_categorie,
                date_debut__gte=aujourd_hui,
                date_debut__lte=fin_mois
            ).delete()

            pharmacies_anciennes = list(P.objects.filter(
                delegation=old_delegation,
                categorie=old_categorie,
                est_active=True
            ).order_by('created_at', 'id'))

            if pharmacies_anciennes:
                j_courant = aujourd_hui
                idx = 0
                while j_courant <= fin_mois:
                    j_semaine = j_courant.weekday()
                    if old_categorie == 'B':
                        for ph in pharmacies_anciennes:
                            GardePharmacie.objects.create(
                                pharmacie=ph,
                                date_debut=j_courant,
                                date_fin=j_courant,
                                type_garde='nuit'
                            )
                    elif old_categorie == 'A' and j_semaine == 6:
                        ph = pharmacies_anciennes[idx % len(pharmacies_anciennes)]
                        GardePharmacie.objects.create(
                            pharmacie=ph,
                            date_debut=j_courant,
                            date_fin=j_courant,
                            type_garde='dimanche'
                        )
                        idx += 1
                    j_courant += timedelta(days=1)
                print(f" [SUCCÈS] Ré-génération équilibrée de l'ancienne délégation {old_delegation.nom} (Cat. {old_categorie})")
        except Delegation.DoesNotExist:
            pass