# pharmacies/views.py
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, date

from pharmacies.filters import PharmacieFilter
from .models import *
from .serializers import *
from .permissions import require_perm 


"""class PharmacieViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pharmacie.objects.filter(
        est_active=True
    ).select_related('delegation__gouvernorat')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['delegation', 'delegation__gouvernorat']
    search_fields = ['nom', 'adresse', 'telephone']
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PharmacieDetailSerializer
        return PharmacieListSerializer"""
class PharmacieViewSet(viewsets.ModelViewSet):
    queryset = Pharmacie.objects.filter(est_active=True).select_related('delegation__gouvernorat')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['delegation', 'delegation__gouvernorat']
    search_fields = ['nom', 'adresse', 'telephone']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'ouvertes', 'garde', 'proches', 'statut']:
            return [AllowAny()]
        elif self.action == 'create':
            return [require_perm('add_pharmacie')()]
        elif self.action in ['update', 'partial_update']:
            return [require_perm('change_pharmacie')()]
        elif self.action == 'destroy':
            return [require_perm('delete_pharmacie')()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PharmacieCreateSerializer
        if self.action == 'retrieve':
            return PharmacieDetailSerializer
        return PharmacieListSerializer

    # ─── GET /api/pharmacies/ouvertes/ ───────────────────────
    @action(detail=False, methods=['get'])
    def ouvertes(self, request):
        now = datetime.now()
        pharmacies = self.get_queryset()
        ouvertes = [
            p for p in pharmacies
            if p.verifier_ouverture(now.date(), now.time())
        ]
        serializer = PharmacieListSerializer(ouvertes, many=True)
        return Response({
            'count': len(ouvertes),
            'pharmacies': serializer.data
        })

    # ─── GET /api/pharmacies/garde/ ──────────────────────────
    @action(detail=False, methods=['get'])
    def garde(self, request):
        today = date.today()
        gardes = GardePharmacie.objects.filter(
            date_debut__lte=today,
            date_fin__gte=today
        ).select_related('pharmacie__delegation__gouvernorat')

        data = []
        for g in gardes:
            p = g.pharmacie
            data.append({
                'id': str(p.id),
                'nom': p.nom,
                'adresse': p.adresse,
                'telephone': p.telephone,
                'latitude': str(p.latitude) if p.latitude else None,
                'longitude': str(p.longitude) if p.longitude else None,
                'delegation': p.delegation.nom if p.delegation else None,
                'type_garde': g.get_type_garde_display(),
                'heure_debut': g.heure_debut,
                'heure_fin': g.heure_fin,
            })
        return Response({'count': len(data), 'pharmacies_garde': data})

    # ─── GET /api/pharmacies/proches/?lat=&lng=&rayon= ───────
    @action(detail=False, methods=['get'])
    def proches(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        rayon = float(request.query_params.get('rayon', 5))

        if not lat or not lng:
            return Response(
                {'erreur': 'Paramètres lat et lng requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        lat, lng = float(lat), float(lng)
        now = datetime.now()
        pharmacies = self.get_queryset()

        resultats = []
        for p in pharmacies:
            dist = p.distance_km(lat, lng)
            if dist <= rayon:
                resultats.append((p, dist))

        resultats.sort(key=lambda x: x[1])

        data = []
        for p, dist in resultats[:20]:
            s = PharmacieListSerializer(p).data
            s['distance_km'] = round(dist, 2)
            s['est_ouverte'] = p.verifier_ouverture(now.date(), now.time())
            data.append(s)

        return Response({'count': len(data), 'pharmacies': data})

    # ─── GET /api/pharmacies/{id}/statut/?date=&heure= ───────
    @action(detail=True, methods=['get'])
    def statut(self, request, pk=None):
        pharmacie = self.get_object()
        date_param = request.query_params.get('date', str(date.today()))
        heure_param = request.query_params.get('heure', datetime.now().strftime('%H:%M'))

        d = datetime.strptime(date_param, '%Y-%m-%d').date()
        h = datetime.strptime(heure_param, '%H:%M').time()

        est_ouverte = pharmacie.verifier_ouverture(d, h)
        jour_ferie = JourFerieTunisie.objects.filter(date=d).first()

        return Response({
            'pharmacie': pharmacie.nom,
            'est_ouverte': est_ouverte,
            'date': date_param,
            'heure': heure_param,
            'jour_ferie': jour_ferie.nom if jour_ferie else None,
        })


# ─── GET /api/jours-feries/?annee= ───────────────────────────
@api_view(['GET'])
def jours_feries_annee(request):
    annee = request.query_params.get('annee', date.today().year)
    jours = JourFerieTunisie.objects.filter(
        date__year=annee
    ).order_by('date')
    serializer = JourFerieSerializer(jours, many=True)
    return Response(serializer.data)


# ─── GET /api/ramadan/ ────────────────────────────────────────
@api_view(['GET'])
def periodes_ramadan(request):
    periodes = PeriodeRamadan.objects.all().order_by('-annee')
    serializer = PeriodeRamadanSerializer(periodes, many=True)
    return Response(serializer.data)

# ─── 1. Liste TOUTES les pharmacies (actives + inactives) pour l'admin ────────
class PharmacieAdminViewSet(viewsets.ModelViewSet):

    queryset = Pharmacie.objects.all().select_related('delegation__gouvernorat')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categorie', 'est_active', 'delegation__gouvernorat']
    search_fields = ['nom', 'adresse', 'telephone']
    permission_classes = [IsAuthenticated]
    queryset = Pharmacie.objects.all().select_related('delegation__gouvernorat','proprietaire')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PharmacieCreateSerializer
        if self.action == 'retrieve':
            return PharmacieDetailSerializer
        return PharmacieListSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.has_perm('pharmacies.view_all_pharmacies') or user.is_staff:
            return Pharmacie.objects.all().select_related('delegation__gouvernorat', 'proprietaire')
        return Pharmacie.objects.all().select_related('delegation__gouvernorat','proprietaire')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]  # contrôle dans perform_update/destroy
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        serializer.save(proprietaire=self.request.user)
        
        
    def perform_update(self, serializer):
        pharmacie = self.get_object()
        user = self.request.user
        # Seul le propriétaire ou admin peut modifier
        if not user.is_staff and str(pharmacie.proprietaire_id) != str(user.id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne pouvez modifier que votre propre pharmacie.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.is_staff and str(instance.proprietaire_id) != str(user.id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne pouvez supprimer que votre propre pharmacie.")
        instance.delete()

    # ─── PATCH /api/admin/pharmacies/{id}/toggle_active/ ─────
    @action(detail=True, methods=['patch'])
    def toggle_active(self, request, pk=None):
        """Active ou désactive une pharmacie"""
        pharmacie = self.get_object()
        pharmacie.est_active = not pharmacie.est_active
        pharmacie.save()
        return Response({
            'message'   : f"Pharmacie {'activée' if pharmacie.est_active else 'désactivée'}.",
            'est_active': pharmacie.est_active
        })


# ─── 2. Stats pour le dashboard ───────────────────────────────────────────────
@api_view(['GET'])
def dashboard_stats(request):
    from django.utils import timezone
    from accounts.models import User

    now        = timezone.now()
    this_month = now.replace(day=1)

    return Response({
        'total_utilisateurs'  : User.objects.count(),
        'nouveaux_ce_mois'    : User.objects.filter(date_joined__gte=this_month).count(),
        'comptes_en_attente'  : User.objects.filter(is_active=False).count(),
        'pharmacies_actives'  : Pharmacie.objects.filter(est_active=True).count(),
        'pharmacies_inactives': Pharmacie.objects.filter(est_active=False).count(),
        'nouvelles_ce_mois'   : Pharmacie.objects.filter(created_at__gte=this_month).count(),
        'gardes_ce_mois': GardePharmacie.objects.filter(
            date_debut__year=now.year,
            date_fin__month=now.month,
        ).count(),
        'roles': {
            'citoyens'        : User.objects.filter(roles__name='citoyen').count(),
            'pharmaciens'     : User.objects.filter(roles__name='pharmacien').count(),
            'administrateurs' : User.objects.filter(roles__name='administrateur').count(),
        }
    })


# ─── 3. CRUD Jours fériés (admin) ─────────────────────────────────────────────
class JourFerieViewSet(viewsets.ModelViewSet):
    queryset         = JourFerieTunisie.objects.all().order_by('date')
    serializer_class = JourFerieSerializer
    permission_classes = [IsAuthenticated]
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['date__year', 'type_ferie']


# ─── 4. CRUD Période Ramadan (admin) ──────────────────────────────────────────
class PeriodeRamadanViewSet(viewsets.ModelViewSet):
    queryset         = PeriodeRamadan.objects.all().order_by('-annee')
    serializer_class = PeriodeRamadanSerializer
    permission_classes = [IsAuthenticated]

