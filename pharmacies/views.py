# pharmacies/views.py
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, date , time
from pharmacies.filters import PharmacieFilter
from .models import *
from .serializers import *
from .permissions import require_perm
from .models import PeriodeRamadan, HoraireTravail



class PharmacieViewSet(viewsets.ModelViewSet):
    queryset = Pharmacie.objects.filter(est_active=True).select_related('delegation__gouvernorat')
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class  = PharmacieFilter                          # ✅ utilise le filtre personnalisé
    search_fields    = ['nom', 'adresse', 'telephone']

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
        return Response({'count': len(ouvertes), 'pharmacies': serializer.data})

    # ─── GET /api/pharmacies/garde/ ──────────────────────────
    @action(detail=False, methods=['get'])
    def garde(self, request):
        today  = date.today()
        gardes = GardePharmacie.objects.filter(
            date_debut__lte=today,
            date_fin__gte=today
        ).select_related('pharmacie__delegation__gouvernorat')

        data = []
        for g in gardes:
            p = g.pharmacie
            data.append({
                'id'         : str(p.id),
                'nom'        : p.nom,
                'adresse'    : p.adresse,
                'telephone'  : p.telephone,
                'latitude'   : str(p.latitude)  if p.latitude  else None,
                'longitude'  : str(p.longitude) if p.longitude else None,
                'delegation' : p.delegation.nom if p.delegation else None,
                'type_garde' : g.get_type_garde_display(),
                'heure_debut': g.heure_debut,
                'heure_fin'  : g.heure_fin,
            })
        return Response({'count': len(data), 'pharmacies_garde': data})

    # ─── GET /api/pharmacies/proches/?lat=&lng=&rayon= ───────
    @action(detail=False, methods=['get'])
    def proches(self, request):
        lat   = request.query_params.get('lat')
        lng   = request.query_params.get('lng')
        rayon = float(request.query_params.get('rayon', 5))

        if not lat or not lng:
            return Response(
                {'erreur': 'Paramètres lat et lng requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        lat, lng   = float(lat), float(lng)
        now        = datetime.now()
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
        pharmacie   = self.get_object()
        date_param  = request.query_params.get('date',  str(date.today()))
        heure_param = request.query_params.get('heure', datetime.now().strftime('%H:%M'))

        d = datetime.strptime(date_param,  '%Y-%m-%d').date()
        h = datetime.strptime(heure_param, '%H:%M').time()

        est_ouverte = pharmacie.verifier_ouverture(d, h)
        jour_ferie  = JourFerieTunisie.objects.filter(date=d).first()

        return Response({
            'pharmacie'  : pharmacie.nom,
            'est_ouverte': est_ouverte,
            'date'       : date_param,
            'heure'      : heure_param,
            'jour_ferie' : jour_ferie.nom if jour_ferie else None,
        })


# ─── Admin ViewSet — toutes les pharmacies ────────────────────
class PharmacieAdminViewSet(viewsets.ModelViewSet):

    filter_backends    = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class    = PharmacieFilter        # ✅ remplace filterset_fields
    search_fields      = ['nom', 'adresse', 'telephone']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pharmacie.objects.all().select_related(
            'delegation__gouvernorat', 'proprietaire'
        )

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PharmacieCreateSerializer
        if self.action == 'retrieve':
            return PharmacieDetailSerializer
        return PharmacieListSerializer

    def get_permissions(self):
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        pharmacie = serializer.save(proprietaire=self.request.user)
        self._generer_horaires(pharmacie)
        
        
    def _generer_horaires(self, pharmacie):
        aujourd_hui = date.today()
        en_ramadan  = PeriodeRamadan.objects.filter(
            date_debut__lte=aujourd_hui,
            date_fin__gte=aujourd_hui
        ).exists()

        if pharmacie.categorie == 'A':
            if en_ramadan:
                horaires = [
                    *[{
                        'jour': j, 'est_ouvert': True,
                        'heure_ouverture': time(8, 30),
                        'heure_fermeture': time(17, 0),
                        'pause_debut': None, 'pause_fin': None,
                    } for j in range(5)],
                    {
                        'jour': 5, 'est_ouvert': True,
                        'heure_ouverture': time(8, 30),
                        'heure_fermeture': time(13, 0),
                        'pause_debut': None, 'pause_fin': None,
                    },
                    {
                        'jour': 6, 'est_ouvert': False,
                        'heure_ouverture': None, 'heure_fermeture': None,
                        'pause_debut': None, 'pause_fin': None,
                    },
                ]
            else:
                horaires = [
                    *[{
                        'jour': j, 'est_ouvert': True,
                        'heure_ouverture': time(8, 30),
                        'heure_fermeture': time(19, 30),
                        'pause_debut':     time(13, 0),
                        'pause_fin':       time(15, 0),
                    } for j in range(5)],
                    {
                        'jour': 5, 'est_ouvert': True,
                        'heure_ouverture': time(8, 30),
                        'heure_fermeture': time(13, 0),
                        'pause_debut': None, 'pause_fin': None,
                    },
                    {
                        'jour': 6, 'est_ouvert': False,
                        'heure_ouverture': None, 'heure_fermeture': None,
                        'pause_debut': None, 'pause_fin': None,
                    },
                ]
        else:
            horaires = [{
                'jour': j, 'est_ouvert': True,
                'heure_ouverture': time(19, 30),
                'heure_fermeture': time(8, 30),
                'pause_debut': None, 'pause_fin': None,
            } for j in range(7)]

        for h in horaires:
            HoraireTravail.objects.get_or_create(
                pharmacie=pharmacie, jour=h['jour'], defaults=h
            )
    def perform_update(self, serializer):
        pharmacie = self.get_object()
        user      = self.request.user
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
        pharmacie            = self.get_object()
        pharmacie.est_active = not pharmacie.est_active
        pharmacie.save()
        return Response({
            'message'   : f"Pharmacie {'activée' if pharmacie.est_active else 'désactivée'}.",
            'est_active': pharmacie.est_active,
        })


# ─── GET /api/jours-feries/?annee= ───────────────────────────
@api_view(['GET'])
def jours_feries_annee(request):
    annee = request.query_params.get('annee', date.today().year)
    jours = JourFerieTunisie.objects.filter(date__year=annee).order_by('date')
    serializer = JourFerieSerializer(jours, many=True)
    return Response(serializer.data)


# ─── GET /api/ramadan/ ────────────────────────────────────────
@api_view(['GET'])
def periodes_ramadan(request):
    periodes   = PeriodeRamadan.objects.all().order_by('-annee')
    serializer = PeriodeRamadanSerializer(periodes, many=True)
    return Response(serializer.data)


# ─── Stats dashboard ──────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
        'gardes_ce_mois'      : GardePharmacie.objects.filter(
            date_debut__year=now.year,
            date_fin__month=now.month,
        ).count(),
        'roles': {
            'citoyens'       : User.objects.filter(roles__name='citoyen').count(),
            'pharmaciens'    : User.objects.filter(roles__name='pharmacien').count(),
            'administrateurs': User.objects.filter(roles__name='administrateur').count(),
        }
    })


# ─── CRUD Jours fériés (admin) ────────────────────────────────
class JourFerieViewSet(viewsets.ModelViewSet):
    queryset           = JourFerieTunisie.objects.all().order_by('date')
    serializer_class   = JourFerieSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['date__year', 'type_ferie']


# ─── CRUD Période Ramadan (admin) ─────────────────────────────
class PeriodeRamadanViewSet(viewsets.ModelViewSet):
    queryset           = PeriodeRamadan.objects.all().order_by('-annee')
    serializer_class   = PeriodeRamadanSerializer
    permission_classes = [IsAuthenticated]