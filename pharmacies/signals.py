# pharmacies/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date, timedelta, time


@receiver(post_save, sender='pharmacies.Pharmacie')
def generer_donnees_pharmacie(sender, instance, created, **kwargs):
    print(f" Signal déclenché ! created={created}, pharmacie={instance.nom}")

    if not created:
        return

    from .models import GardePharmacie, HoraireRamadan, PeriodeRamadan, HoraireTravail, Pharmacie as P

    # ── 1. Horaires de travail ─────────────────────────────────
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
    print(f" Horaires de travail créés")

    # ── 2. Horaires Ramadan (seulement cat A) ──────────────────
    if instance.categorie == 'A':
        periode = PeriodeRamadan.objects.filter(
            date_fin__gte=date.today()
        ).first()
        print(f"🌙 Période Ramadan trouvée : {periode}")

        if periode:
            # Horaires CNOPT officiels Ramadan
            # Lun→Ven : 08h30→17h00 (tranche unique)
            # Samedi  : 08h30→13h00
            # Dimanche: fermé
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
            print(f" Horaires Ramadan CNOPT créés")

    # ── 3. Gardes du mois courant ──────────────────────────────
    aujourd_hui = date.today()
    if aujourd_hui.month == 12:
        fin_mois = date(aujourd_hui.year + 1, 1, 1) - timedelta(days=1)
    else:
        fin_mois = date(aujourd_hui.year, aujourd_hui.month + 1, 1) - timedelta(days=1)

    nb_pharmacies = P.objects.filter(
        delegation=instance.delegation,
        categorie=instance.categorie,
        est_active=True
    ).count()

    jour_courant = aujourd_hui
    index        = nb_pharmacies - 1
    gardes_creees = 0

    while jour_courant <= fin_mois:
        jour_semaine = jour_courant.weekday()

        # ── Cat B : garde chaque nuit ──────────────────────────
        if instance.categorie == 'B':
            pharmacies_B = list(P.objects.filter(
                delegation=instance.delegation,
                categorie='B',
                est_active=True
            ).order_by('created_at'))

            if pharmacies_B and pharmacies_B[index % len(pharmacies_B)].id == instance.id:
                GardePharmacie.objects.get_or_create(
                    pharmacie=instance,
                    date_debut=jour_courant,
                    date_fin=jour_courant,
                    defaults={'type_garde': 'nuit'}
                )
                gardes_creees += 1

        # ── Cat A : garde le dimanche uniquement ───────────────
        elif instance.categorie == 'A' and jour_semaine == 6:
            pharmacies_A = list(P.objects.filter(
                delegation=instance.delegation,
                categorie='A',
                est_active=True
            ).order_by('created_at'))

            if pharmacies_A and pharmacies_A[index % len(pharmacies_A)].id == instance.id:
                GardePharmacie.objects.get_or_create(
                    pharmacie=instance,
                    date_debut=jour_courant,
                    date_fin=jour_courant,
                    defaults={'type_garde': 'dimanche'}
                )
                gardes_creees += 1

        jour_courant += timedelta(days=1)

    print(f"{gardes_creees} gardes créées pour {instance.nom}")