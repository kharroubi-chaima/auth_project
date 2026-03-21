from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import F
from datetime import date, timedelta

from .models import Medicament, Categorie, MouvementStock, StockPharmacie, Vente
from .serializers import (
    MedicamentSerializer, CategorieSerializer,
    MouvementStockSerializer, StockPharmacieSerializer,
    VenteSerializer,
)
from .permissions import IsAdminRole


# ── Catégories ────────────────────────────────────────────────────────────────

class CategorieViewSet(viewsets.ModelViewSet):
    queryset           = Categorie.objects.all()
    serializer_class   = CategorieSerializer
    permission_classes = [IsAuthenticated]


# ── Médicaments ───────────────────────────────────────────────────────────────

class MedicamentViewSet(viewsets.ModelViewSet):
    queryset           = Medicament.objects.select_related('categorie').all()
    serializer_class   = MedicamentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['categorie', 'ordonnance_requise']
    search_fields      = ['nom', 'dci']
    ordering_fields    = ['nom', 'prix_vente', 'date_expiration', 'quantite_stock']

    @action(detail=False, methods=['get'], url_path='expirent-bientot')
    def expirent_bientot(self, request):
        qs = Medicament.objects.filter(
            date_expiration__lte=date.today() + timedelta(days=30)
        ).select_related('categorie')
        return Response(MedicamentSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='stock-faible')
    def stock_faible(self, request):
        qs = Medicament.objects.filter(
            quantite_stock__lte=F('seuil_alerte')
        ).select_related('categorie')
        return Response(MedicamentSerializer(qs, many=True).data)


# ── Stock par pharmacie ───────────────────────────────────────────────────────

class StockPharmacieViewSet(viewsets.ModelViewSet):
    serializer_class   = StockPharmacieSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['pharmacie', 'medicament', 'medicament__categorie']
    search_fields      = ['medicament__nom', 'medicament__dci']
    ordering_fields    = ['quantite_stock', 'seuil_alerte', 'medicament__nom']

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        base_qs = StockPharmacie.objects.select_related(
            'pharmacie', 'medicament', 'medicament__categorie'
        )
        if self._est_admin():
            return base_qs.all()
        return base_qs.filter(pharmacie__proprietaire=self.request.user)

    @action(detail=False, methods=['get'], url_path='alertes')
    def alertes(self, request):
        qs             = self.get_queryset()
        stock_faible   = qs.filter(quantite_stock__lte=F('seuil_alerte'))
        date_limite    = date.today() + timedelta(days=30)
        expire_bientot = qs.filter(medicament__date_expiration__lte=date_limite)
        return Response({
            'stock_faible'   : StockPharmacieSerializer(stock_faible,   many=True).data,
            'expire_bientot' : StockPharmacieSerializer(expire_bientot, many=True).data,
        })

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        stock      = self.get_object()
        mouvements = stock.mouvements.select_related('created_by').all()
        return Response(MouvementStockSerializer(mouvements, many=True).data)


# ── Mouvements ────────────────────────────────────────────────────────────────

class MouvementStockViewSet(viewsets.ModelViewSet):
    serializer_class   = MouvementStockSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, OrderingFilter]
    filterset_fields   = ['stock', 'stock__pharmacie', 'stock__medicament', 'type']
    http_method_names  = ['get', 'post']

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        base_qs = MouvementStock.objects.select_related(
            'stock__medicament', 'stock__pharmacie', 'created_by'
        )
        if self._est_admin():
            return base_qs.all()
        return base_qs.filter(stock__pharmacie__proprietaire=self.request.user)

    def perform_create(self, serializer):
        user  = self.request.user
        stock = serializer.validated_data.get('stock')
        if not self._est_admin():
            if stock.pharmacie.proprietaire != user:
                raise PermissionDenied(
                    "Vous ne pouvez pas créer un mouvement pour une autre pharmacie."
                )
        serializer.save(created_by=user)


# ── Ventes ────────────────────────────────────────────────────────────────────

class VenteViewSet(viewsets.ModelViewSet):
    serializer_class   = VenteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, OrderingFilter]
    filterset_fields   = ['pharmacie']
    ordering_fields    = ['created_at', 'total']
    # ✅ Lecture + création uniquement — pas de modification/suppression d'une vente
    http_method_names  = ['get', 'post']

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        base_qs = Vente.objects.prefetch_related(
            'lignes__medicament'
        ).select_related('pharmacie', 'created_by')

        if self._est_admin():
            return base_qs.all()
        # Pharmacien → uniquement ses propres ventes
        return base_qs.filter(pharmacie__proprietaire=self.request.user)

    def get_serializer_context(self):
        # ✅ Passe le request au serializer pour récupérer la pharmacie
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Statistiques rapides : total ventes du jour, de la semaine, du mois."""
        from django.db.models import Sum, Count
        from datetime import datetime

        qs          = self.get_queryset()
        aujourd_hui = date.today()

        debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        debut_mois    = aujourd_hui.replace(day=1)

        def agg(queryset):
            r = queryset.aggregate(
                nb_ventes  = Count('id'),
                total_ca   = Sum('total'),
            )
            return {
                'nb_ventes' : r['nb_ventes']  or 0,
                'total_ca'  : float(r['total_ca'] or 0),
            }

        return Response({
            'aujourd_hui' : agg(qs.filter(created_at__date=aujourd_hui)),
            'semaine'     : agg(qs.filter(created_at__date__gte=debut_semaine)),
            'mois'        : agg(qs.filter(created_at__date__gte=debut_mois)),
        })