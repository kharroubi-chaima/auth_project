# dashboard/views_superadmin.py
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta, date

from rest_framework.views import APIView
from rest_framework.response import Response

from stock.models import StockPharmacie, Medicament, Vente, LigneVente
from reservations.models import Reservation
from urgences.models import DemandeUrgente
from pharmacies.models import Pharmacie

from .permissions import EstSuperAdmin


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pharmacie_filter(request):
    """
    Retourne un dict de filtre sur pharmacie_id si le superadmin
    passe ?pharmacie_id=X en query param (vue mono-pharmacie).
    Sinon retourne {} → toutes pharmacies actives.
    """
    pid = request.query_params.get('pharmacie_id')
    if pid:
        return {'pharmacie_id': pid, 'pharmacie__est_active': True}
    return {'pharmacie__est_active': True}


def _vente_filter(request):
    """Même logique pour le modèle Vente (ForeignKey directe)."""
    pid = request.query_params.get('pharmacie_id')
    if pid:
        return {'pharmacie_id': pid, 'pharmacie__est_active': True}
    return {'pharmacie__est_active': True}

def _reservation_filter(request):
    """Filtre pour Reservation (pharmacie accessible via stock__pharmacie)."""
    pid = request.query_params.get('pharmacie_id')
    if pid:
        return {'stock__pharmacie_id': pid, 'stock__pharmacie__est_active': True}
    return {'stock__pharmacie__est_active': True}


# ─────────────────────────────────────────────────────────────────────────────
# KPIs globaux
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminKPIView(APIView):
    """
    GET /api/superadmin/dashboard/kpis/
    KPIs globaux compatibles avec le frontend Angular
    """
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        today = date.today()
        now = timezone.now()

        f = _pharmacie_filter(request)
        vf = _vente_filter(request)
        rf = _reservation_filter(request)

        debut_mois = today.replace(day=1)

        # ── Pharmacies ─────────────────────────────
        total_pharmacies = Pharmacie.objects.filter(est_active=True).count()
        nouvelles_ce_mois = Pharmacie.objects.filter(
            est_active=True,
            created_at__date__gte=debut_mois
        ).count()

        # ── Utilisateurs ───────────────────────────
        total_users = User.objects.count()
        nouveaux_users = User.objects.filter(
            date_joined__date__gte=debut_mois
        ).count()
        actifs_30j = User.objects.filter(
            last_login__gte=now - timedelta(days=30)
        ).count()

        # ── CA ─────────────────────────────────────
        ca_jour = (
            Vente.objects
            .filter(**vf, created_at__date=today)
            .aggregate(total=Sum('total'))['total'] or 0
        )

        ca_mois = (
            Vente.objects
            .filter(**vf, created_at__date__gte=debut_mois)
            .aggregate(total=Sum('total'))['total'] or 0
        )

        # ── Réservations ───────────────────────────
        reservations_actives = (
            Reservation.objects
            .filter(**rf, statut='active', expire_at__gt=now)
            .count()
        )

        reservations_mois = (
            Reservation.objects
            .filter(created_at__date__gte=debut_mois)
            .count()
        )

        # ── Stocks ─────────────────────────────────
        stocks = StockPharmacie.objects.filter(**f).select_related('medicament')

        stock_faible = sum(1 for s in stocks if s.stock_faible)
        ruptures = sum(1 for s in stocks if s.en_rupture)

        expiration_seuil = today + timedelta(days=30)
        expirations = (
            StockPharmacie.objects
            .filter(
                **f,
                medicament__date_expiration__lte=expiration_seuil,
                medicament__date_expiration__gte=today
            )
            .count()
        )

        # ── Demandes urgentes ──────────────────────
        demandes_urgentes = (
            DemandeUrgente.objects
            .filter(created_at__date__gte=debut_mois)
            .count()
        )

        demandes_en_attente = (
            DemandeUrgente.objects
            .filter(statut='en_attente')
            .count()
        )

        # ── Response finale compatible Angular ─────
        return Response({
            "pharmacies": {
                "total": total_pharmacies,
                "actives": total_pharmacies,
                "inactives": 0,
                "nouvelles_mois": nouvelles_ce_mois,
            },
            "utilisateurs": {
                "total": total_users,
                "nouveaux_mois": nouveaux_users,
                "actifs_30j": actifs_30j,
            },
            "ca": {
                "jour": float(ca_jour),
                "mois": float(ca_mois),
                "evolution": 0  # tu peux améliorer après
            },
            "stocks": {
                "ruptures": ruptures,
                "stock_faible": stock_faible,
                "expirations_30j": expirations,
            },
            "reservations": {
                "actives": reservations_actives,
                "mois": reservations_mois,
            },
            "demandes": {
                "mois": demandes_urgentes,
                "en_attente": demandes_en_attente,
            }
        })
# ─────────────────────────────────────────────────────────────────────────────
# Liste des pharmacies avec leurs KPIs
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminPharmaciesKPIView(APIView):
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        today = date.today()
        now = timezone.now()

        pharmacies = Pharmacie.objects.filter(est_active=True).select_related('proprietaire')

        result = []

        for p in pharmacies:
            stocks = StockPharmacie.objects.filter(pharmacie=p)

            ca_jour = Vente.objects.filter(
                pharmacie=p,
                created_at__date=today
            ).aggregate(total=Sum('total'))['total'] or 0

            ruptures = sum(1 for s in stocks if s.en_rupture)

            reservations_actives = Reservation.objects.filter(
                stock__pharmacie=p,
                statut='active',
                expire_at__gt=now
            ).count()

            result.append({
                'id': p.id,
                'nom': p.nom,
                'proprietaire': p.proprietaire.get_full_name() or p.proprietaire.username,
                'ca_jour': float(ca_jour),
                'ruptures': ruptures,
                'reservations_actives': reservations_actives,
            })

        result.sort(key=lambda x: x['ca_jour'], reverse=True)

        return Response({
            "count": len(result),
            "pharmacies": result
        })
# ─────────────────────────────────────────────────────────────────────────────
# Ventes journalières globales
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminVentesJournalieresView(APIView):
    """
    GET /api/superadmin/dashboard/ventes/?period=7&pharmacie_id=<int>
    CA par jour, toutes pharmacies ou une seule.
    """
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        try:
            period = int(request.query_params.get('period', 7))
            period = max(1, min(period, 90))
        except ValueError:
            period = 7

        vf    = _vente_filter(request)
        today = date.today()
        result = []

        for i in range(period - 1, -1, -1):
            jour = today - timedelta(days=i)
            ca   = (
                Vente.objects
                .filter(**vf, created_at__date=jour)
                .aggregate(total=Sum('total'))['total'] or 0
            )
            result.append({
                'date':  jour.isoformat(),
                'label': jour.strftime('%a %d/%m'),
                'ca':    float(ca),
            })

        return Response({'period': period, 'data': result})


# ─────────────────────────────────────────────────────────────────────────────
# Stats réservations globales
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminReservationsStatsView(APIView):
    """
    GET /api/superadmin/dashboard/reservations/stats/?pharmacie_id=<int>
    Comptage par statut + taux de récupération sur 30 jours.
    """
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        debut = timezone.now() - timedelta(days=30)
        rf     = _reservation_filter(request)

        qs = (
            Reservation.objects
            .filter(**rf, created_at__gte=debut)
            .values('statut')
            .annotate(count=Count('id'))
        )

        stats           = {row['statut']: row['count'] for row in qs}
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
# Stats demandes urgentes globales
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminDemandesStatsView(APIView):
    """
    GET /api/superadmin/dashboard/demandes/stats/?pharmacie_id=<int>
    Comptage par type et statut sur le mois en cours.
    """
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        debut_mois = date.today().replace(day=1)
        pid        = request.query_params.get('pharmacie_id')

        base_filter = {'pharmacie__est_active': True, 'created_at__date__gte': debut_mois}
        if pid:
            base_filter['pharmacie_id'] = pid

        qs_type = (
            DemandeUrgente.objects
            .filter(**base_filter)
            .values('type_demande')
            .annotate(count=Count('id'))
        )

        qs_statut = (
            DemandeUrgente.objects
            .filter(**base_filter)
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
# Alertes stock globales
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminAlertesStockView(APIView):
    """
    GET /api/superadmin/dashboard/alertes/?pharmacie_id=<int>
    Toutes les alertes de stock (rupture > faible > expiration),
    enrichies du nom de la pharmacie.
    """
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        today            = date.today()
        expiration_seuil = today + timedelta(days=30)
        f                = _pharmacie_filter(request)

        stocks = (
            StockPharmacie.objects
            .filter(**f)
            .select_related('medicament', 'pharmacie')
        )

        alertes = []
        for s in stocks:
            med = s.medicament

            if s.en_rupture:
                alertes.append({
                    'pharmacie': s.pharmacie.nom,
                    'medicament': med.nom,
                    'type':       'rupture',
                    'priorite':   1,
                    'detail':     'Stock épuisé',
                    'quantite':   0,
                    'seuil':      s.seuil_alerte,
                })
            elif s.stock_faible:
                alertes.append({
                    'pharmacie': s.pharmacie.nom,
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
                    'pharmacie':       s.pharmacie.nom,
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
# Top 5 médicaments vendus (global)
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminTop5MedicamentsView(APIView):
    """
    GET /api/superadmin/dashboard/top-medicaments/?period=30&pharmacie_id=<int>
    Top 5 médicaments les plus vendus sur la période.
    """
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        try:
            period = int(request.query_params.get('period', 30))
            period = max(1, min(period, 365))
        except ValueError:
            period = 30

        debut = date.today() - timedelta(days=period)
        vf    = _vente_filter(request)

        top = (
            LigneVente.objects
            .filter(
                vente__created_at__date__gte=debut,
                **{f'vente__{k}': v for k, v in vf.items()}
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
        
from django.contrib.auth import get_user_model
User = get_user_model()


class SuperAdminNouvellesPharmaciesView(APIView):
    """GET /api/superadmin/dashboard/nouvelles-pharmacies/"""
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        qs = (
            Pharmacie.objects
            .select_related('proprietaire')
            .order_by('-created_at')[:10]
        )
        data = [
            {
                'id':           p.id,
                'nom':          p.nom,
                'est_active':   p.est_active,
                'proprietaire': getattr(p.proprietaire, 'get_full_name', lambda: '')() or getattr(p.proprietaire, 'email', '') or str(p.proprietaire),
                'gouvernorat':  getattr(p, 'gouvernorat', None),
                'created_at':   p.created_at.strftime('%d/%m/%Y'),
            }
            for p in qs
        ]
        return Response({'data': data})


class SuperAdminInscriptionsView(APIView):
    """GET /api/superadmin/dashboard/inscriptions/?period=30"""
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        try:
            period = int(request.query_params.get('period', 30))
            period = max(1, min(period, 90))
        except ValueError:
            period = 30

        today  = date.today()
        result = []
        for i in range(period - 1, -1, -1):
            jour  = today - timedelta(days=i)
            count = User.objects.filter(date_joined__date=jour).count()
            result.append({
                'date':  jour.isoformat(),
                'label': jour.strftime('%a %d/%m'),
                'count': count,
            })
        return Response({'period': period, 'data': result})


class SuperAdminTopPharmaciesView(APIView):
    """GET /api/superadmin/dashboard/top-pharmacies/?period=30"""
    permission_classes = [EstSuperAdmin]

    def get(self, request):
        try:
            period = int(request.query_params.get('period', 30))
            period = max(1, min(period, 365))
        except ValueError:
            period = 30

        debut = date.today() - timedelta(days=period)
        top = (
            Vente.objects
            .filter(pharmacie__est_active=True, created_at__date__gte=debut)
            .values('pharmacie_id', 'pharmacie__nom')
            .annotate(ca=Sum('total'), nb_ventes=Count('id'))
            .order_by('-ca')[:5]
        )
        return Response({
            'periode_jours': period,
            'data': [
                {
                    'pharmacie_id': row['pharmacie_id'],
                    'pharmacie':    row['pharmacie__nom'],
                    'ca':           float(row['ca']),
                    'nb_ventes':    row['nb_ventes'],
                }
                for row in top
            ],
        })