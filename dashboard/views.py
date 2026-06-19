# dashboard/views.py
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta, date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from stock.models import StockPharmacie, Medicament, Vente, LigneVente
from reservations.models import Reservation
from urgences.models import DemandeUrgente
from pharmacies.models import Pharmacie


def get_pharmacie(user):
    """Retourne la pharmacie de l'utilisateur (propriétaire ou pharmacien employé)."""
    pharmacie = Pharmacie.objects.filter(proprietaire=user, est_active=True).first()
    if pharmacie:
        return pharmacie
    return user.pharmacies_travail.filter(est_active=True).first()


# ─────────────────────────────────────────────────────────────────────────────
# KPIs généraux
# ─────────────────────────────────────────────────────────────────────────────

class KPIGenerauxView(APIView):
    """
    GET /api/dashboard/kpis/
    Aggrégats généraux : stocks, CA du jour, réservations actives,
    demandes urgentes du mois.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"DEBUG: KPIGenerauxView hit by user {request.user}")
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            print(f"DEBUG: No pharmacie found for user {request.user}")
            return Response({'detail': f'Aucune pharmacie trouvée pour l\'utilisateur {request.user.email}.'}, status=404)

        today = date.today()
        now   = timezone.now()

        stocks = StockPharmacie.objects.filter(pharmacie=pharmacie)

        # CA du jour
        ca_jour = (
            Vente.objects
            .filter(pharmacie=pharmacie, created_at__date=today)
            .aggregate(total=Sum('total'))['total'] or 0
        )

        # Réservations actives (non expirées côté DB)
        reservations_actives = (
            Reservation.objects
            .filter(stock__pharmacie=pharmacie, statut='active', expire_at__gt=now)
            .count()
        )

        # Stock faible
        stock_faible = sum(1 for s in stocks if s.stock_faible)

        # Ruptures
        ruptures = sum(1 for s in stocks if s.en_rupture)

        # Expirations proches (< 30 j)
        expiration_seuil = today + timedelta(days=30)
        expirations = (
            stocks
            .filter(
                medicament__date_expiration__lte=expiration_seuil,
                medicament__date_expiration__gte=today
            )
            .count()
        )

        # Demandes urgentes reçues ce mois
        debut_mois = today.replace(day=1)
        demandes_urgentes = (
            DemandeUrgente.objects
            .filter(pharmacie=pharmacie, created_at__date__gte=debut_mois)
            .count()
        )

        return Response({
            'ca_jour':              float(ca_jour),
            'reservations_actives': reservations_actives,
            'stock_faible':         stock_faible,
            'ruptures':             ruptures,
            'expirations_proches':  expirations,
            'demandes_urgentes':    demandes_urgentes,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Ventes journalières
# ─────────────────────────────────────────────────────────────────────────────

class VentesJournalieresView(APIView):
    """
    GET /api/dashboard/ventes/?period=7   (défaut 7, max 90 jours)
    CA par jour sur la période demandée.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"DEBUG: View hit by {request.user}")
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            print(f"DEBUG: No pharmacie found for {request.user}")
            return Response({'detail': f'Aucune pharmacie trouvée pour {request.user.email}.'}, status=404)

        try:
            period = int(request.query_params.get('period', 7))
            period = max(1, min(period, 90))
        except ValueError:
            period = 7

        today  = date.today()
        result = []

        for i in range(period - 1, -1, -1):
            jour = today - timedelta(days=i)
            ca   = (
                Vente.objects
                .filter(pharmacie=pharmacie, created_at__date=jour)
                .aggregate(total=Sum('total'))['total'] or 0
            )
            result.append({
                'date':  jour.isoformat(),
                'label': jour.strftime('%a %d/%m'),
                'ca':    float(ca),
            })

        return Response({'period': period, 'data': result})


# ─────────────────────────────────────────────────────────────────────────────
# Statistiques réservations
# ─────────────────────────────────────────────────────────────────────────────

class ReservationsStatsView(APIView):
    """
    GET /api/dashboard/reservations/stats/
    Comptage par statut + taux de récupération sur 30 jours.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"DEBUG: View hit by {request.user}")
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            print(f"DEBUG: No pharmacie found for {request.user}")
            return Response({'detail': f'Aucune pharmacie trouvée pour {request.user.email}.'}, status=404)

        debut = timezone.now() - timedelta(days=30)

        qs = (
            Reservation.objects
            .filter(stock__pharmacie=pharmacie, created_at__gte=debut)
            .values('statut')
            .annotate(count=Count('id'))
        )

        stats = {row['statut']: row['count'] for row in qs}

        recuperees      = stats.get('recuperee', 0)
        total_terminees = recuperees + stats.get('expiree', 0) + stats.get('annulee', 0)
        taux            = round(recuperees / total_terminees * 100) if total_terminees else 0

        return Response({
            'periode_jours': 30,
            'par_statut': {
                'active':    stats.get('active', 0),
                'recuperee': recuperees,
                'expiree':   stats.get('expiree', 0),
                'annulee':   stats.get('annulee', 0),
            },
            'taux_recuperation': taux,
            'total': sum(stats.values()),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Statistiques demandes urgentes
# ─────────────────────────────────────────────────────────────────────────────

class DemandesStatsView(APIView):
    """
    GET /api/dashboard/demandes/stats/
    Comptage par type et par statut sur le mois en cours.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"DEBUG: View hit by {request.user}")
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            print(f"DEBUG: No pharmacie found for {request.user}")
            return Response({'detail': f'Aucune pharmacie trouvée pour {request.user.email}.'}, status=404)

        debut_mois = date.today().replace(day=1)

        qs_type = (
            DemandeUrgente.objects
            .filter(pharmacie=pharmacie, created_at__date__gte=debut_mois)
            .values('type_demande')
            .annotate(count=Count('id'))
        )

        qs_statut = (
            DemandeUrgente.objects
            .filter(pharmacie=pharmacie, created_at__date__gte=debut_mois)
            .values('statut')
            .annotate(count=Count('id'))
        )

        par_type   = {row['type_demande']: row['count'] for row in qs_type}
        par_statut = {row['statut']:       row['count'] for row in qs_statut}

        return Response({
            'par_type': {
                'medicament': par_type.get('medicament', 0),
                'service':    par_type.get('service', 0),
            },
            'par_statut': {
                'en_attente': par_statut.get('en_attente', 0),
                'acceptee':   par_statut.get('acceptee', 0),
                'refusee':    par_statut.get('refusee', 0),
                'expiree':    par_statut.get('expiree', 0),
            },
        })


# ─────────────────────────────────────────────────────────────────────────────
# Alertes stock
# ─────────────────────────────────────────────────────────────────────────────

class AlertesStockView(APIView):
    """
    GET /api/dashboard/alertes/
    Liste triée des médicaments à risque :
    rupture (priorité 1) > stock faible (2) > expiration proche (3).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"DEBUG: View hit by {request.user}")
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            print(f"DEBUG: No pharmacie found for {request.user}")
            return Response({'detail': f'Aucune pharmacie trouvée pour {request.user.email}.'}, status=404)

        today            = date.today()
        expiration_seuil = today + timedelta(days=30)

        stocks = (
            StockPharmacie.objects
            .filter(pharmacie=pharmacie)
            .select_related('medicament')
        )

        alertes = []
        for s in stocks:
            med = s.medicament

            if s.en_rupture:
                alertes.append({
                    'medicament': med.nom,
                    'type':       'rupture',
                    'priorite':   1,
                    'detail':     'Stock épuisé',
                    'quantite':   0,
                    'seuil':      s.seuil_alerte,
                })
            elif s.stock_faible:
                alertes.append({
                    'medicament': med.nom,
                    'type':       'stock_faible',
                    'priorite':   2,
                    'detail':     f'Stock : {s.quantite_stock} unités (seuil : {s.seuil_alerte})',
                    'quantite':   s.quantite_stock,
                    'seuil':      s.seuil_alerte,
                })

            if (
                med.date_expiration
                and today <= med.date_expiration <= expiration_seuil
                and s.quantite_stock > 0
            ):
                alertes.append({
                    'medicament':      med.nom,
                    'type':            'expiration',
                    'priorite':        3,
                    'detail':          f'Expire le {med.date_expiration.strftime("%d/%m/%Y")}',
                    'date_expiration': med.date_expiration.isoformat(),
                    'quantite':        s.quantite_stock,
                })

        alertes.sort(key=lambda a: a['priorite'])
        return Response({'count': len(alertes), 'alertes': alertes})


# ─────────────────────────────────────────────────────────────────────────────
# Top 5 médicaments vendus
# ─────────────────────────────────────────────────────────────────────────────

class Top5MedicamentsView(APIView):
    """
    GET /api/dashboard/top-medicaments/?period=30
    Top 5 médicaments les plus vendus sur la période (défaut 30j, max 365j).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)

        try:
            period = int(request.query_params.get('period', 30))
            period = max(1, min(period, 365))
        except ValueError:
            period = 30

        debut = date.today() - timedelta(days=period)

        top = (
            LigneVente.objects
            .filter(
                vente__pharmacie=pharmacie,
                vente__created_at__date__gte=debut
            )
            .values('medicament__nom')
            .annotate(total_vendu=Sum('quantite'))
            .order_by('-total_vendu')[:5]
        )

        return Response({
            'periode_jours': period,
            'data': [
                {
                    'medicament': row['medicament__nom'],
                    'quantite':   row['total_vendu'],
                }
                for row in top
            ],
        })


# ─────────────────────────────────────────────────────────────────────────────
# Rapports Personnalisés (Gérant)
# ─────────────────────────────────────────────────────────────────────────────

class VentesParPharmacienView(APIView):
    """
    GET /api/dashboard/ventes-par-pharmacien/?date_debut=YYYY-MM-DD&date_fin=YYYY-MM-DD
    Retourne le CA généré par chaque employé (pharmacien) de la pharmacie.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)

        date_debut_str = request.query_params.get('date_debut')
        date_fin_str = request.query_params.get('date_fin')

        qs = Vente.objects.filter(pharmacie=pharmacie)

        if date_debut_str:
            try:
                debut = date.fromisoformat(date_debut_str)
                qs = qs.filter(created_at__date__gte=debut)
            except ValueError:
                pass
        if date_fin_str:
            try:
                fin = date.fromisoformat(date_fin_str)
                qs = qs.filter(created_at__date__lte=fin)
            except ValueError:
                pass

        qs = (
            qs.values('created_by__first_name', 'created_by__last_name', 'created_by__email')
            .annotate(ca=Sum('total'))
            .order_by('-ca')
        )

        data = []
        for row in qs:
            fname = row.get('created_by__first_name') or ''
            lname = row.get('created_by__last_name') or ''
            nom = f"{fname} {lname}".strip()
            if not nom:
                nom = row.get('created_by__email') or 'Inconnu'
                
            data.append({
                'pharmacien': nom,
                'ca': float(row['ca'] or 0)
            })

        return Response({'data': data})


class ListeMedicamentsPharmacieView(APIView):
    """
    GET /api/dashboard/medicaments-liste/
    Retourne la liste (id, nom) des médicaments présents dans le stock de la pharmacie.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)

        stocks = StockPharmacie.objects.filter(pharmacie=pharmacie).select_related('medicament')
        data = [{'id': s.medicament.id, 'nom': s.medicament.nom} for s in stocks]
        
        # Tri alphabétique par nom
        data.sort(key=lambda x: x['nom'].lower())
        
        return Response({'data': data})


class ComparaisonMedicamentsView(APIView):
    """
    GET /api/dashboard/comparaison-medicaments/?med1=ID&med2=ID&date_debut=YYYY-MM-DD&date_fin=YYYY-MM-DD
    Retourne l'historique quotidien des ventes (CA) pour les deux médicaments.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacie = get_pharmacie(request.user)
        if not pharmacie:
            return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)

        med1_id = request.query_params.get('med1')
        med2_id = request.query_params.get('med2')
        date_debut_str = request.query_params.get('date_debut')
        date_fin_str = request.query_params.get('date_fin')

        if not med1_id or not med2_id:
            return Response({'detail': 'Veuillez spécifier deux médicaments (med1 et med2).'}, status=400)
            
        try:
            med1_id = int(med1_id)
            med2_id = int(med2_id)
        except ValueError:
             return Response({'detail': 'Identifiants de médicaments invalides.'}, status=400)

        # Détermination des dates
        today = date.today()
        debut = today - timedelta(days=30)
        fin = today
        
        if date_debut_str:
            try:
                debut = date.fromisoformat(date_debut_str)
            except ValueError:
                pass
        if date_fin_str:
            try:
                fin = date.fromisoformat(date_fin_str)
            except ValueError:
                pass

        if fin < debut:
            fin = debut

        # Générer la liste des jours
        jours = []
        courant = debut
        while courant <= fin:
            jours.append(courant)
            courant += timedelta(days=1)
            
        # Noms des médicaments
        noms = {}
        meds = Medicament.objects.filter(id__in=[med1_id, med2_id])
        for m in meds:
            noms[m.id] = m.nom

        # Ventes med1
        from django.db.models import F
        qs1 = LigneVente.objects.filter(
            vente__pharmacie=pharmacie,
            medicament_id=med1_id,
            vente__created_at__date__gte=debut,
            vente__created_at__date__lte=fin
        ).values('vente__created_at__date').annotate(
            ca=Sum(F('quantite') * F('prix_unitaire'))
        )
        
        # Ventes med2
        qs2 = LigneVente.objects.filter(
            vente__pharmacie=pharmacie,
            medicament_id=med2_id,
            vente__created_at__date__gte=debut,
            vente__created_at__date__lte=fin
        ).values('vente__created_at__date').annotate(
            ca=Sum(F('quantite') * F('prix_unitaire'))
        )

        # Indexer par date
        dict_med1 = { row['vente__created_at__date']: row['ca'] for row in qs1 }
        dict_med2 = { row['vente__created_at__date']: row['ca'] for row in qs2 }

        data = []
        for jour in jours:
            ca1 = dict_med1.get(jour, 0)
            ca2 = dict_med2.get(jour, 0)
            data.append({
                'date': jour.isoformat(),
                'label': jour.strftime('%d/%m'),
                'med1_ca': float(ca1),
                'med2_ca': float(ca2),
            })

        return Response({
            'med1_nom': noms.get(med1_id, f'Médicament {med1_id}'),
            'med2_nom': noms.get(med2_id, f'Médicament {med2_id}'),
            'data': data
        })