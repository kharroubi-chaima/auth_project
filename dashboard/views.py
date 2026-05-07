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