from rest_framework import request, viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, date, time
from pharmacies.filters import PharmacieFilter
from .models import *
from .serializers import *
from .permissions import require_perm
from .models import PeriodeRamadan, HoraireTravail
from accounts.permissions import IsSuperAdmin
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()

class PharmacieViewSet(viewsets.ModelViewSet):
    queryset = Pharmacie.objects.filter(est_active=True).select_related('delegation__gouvernorat')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PharmacieFilter
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

    @action(detail=False, methods=['get'])
    def ouvertes(self, request):
        now = datetime.now()
        pharmacies = self.get_queryset()
        ouvertes = [p for p in pharmacies if p.verifier_ouverture(now.date(), now.time())]
        serializer = PharmacieListSerializer(ouvertes, many=True)
        return Response({'count': len(ouvertes), 'pharmacies': serializer.data})

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

# Ajoute ceci en dehors de toute classe (comme mes_pharmaciens)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ma_pharmacie(request):
    # Propriétaire en premier
    pharmacie = Pharmacie.objects.filter(
        proprietaire=request.user
    ).select_related('delegation__gouvernorat').first()
    
    # Sinon admin/pharmacien rattaché
    if not pharmacie:
        pharmacie = request.user.pharmacies_travail.select_related('delegation__gouvernorat').first()
    
    if not pharmacie:
        return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)
    
    return Response(PharmacieAdminSerializer(pharmacie).data)


class GardePharmacieViewSet(viewsets.ModelViewSet):
    serializer_class = GardePharmacieSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.roles.filter(name='administrateur').exists():
            qs = GardePharmacie.objects.all().select_related('pharmacie__delegation__gouvernorat').order_by('date_debut')
            
            gouvernorat_id = self.request.query_params.get('pharmacie__delegation__gouvernorat')
            if gouvernorat_id:
                qs = qs.filter(pharmacie__delegation__gouvernorat_id=gouvernorat_id)
                
            pharmacie_id = self.request.query_params.get('pharmacie')
            if pharmacie_id:
                qs = qs.filter(pharmacie_id=pharmacie_id)
            return qs
        
        # Admin/propriétaire : gardes de SA pharmacie
        pharmacie = Pharmacie.objects.filter(
            proprietaire=user
        ).first()
        
        if not pharmacie:
            pharmacie = user.pharmacies_travail.first()
        if not pharmacie:
            return GardePharmacie.objects.none()
        return GardePharmacie.objects.filter(
            pharmacie=pharmacie
        ).order_by('date_debut')

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("La création manuelle de garde n'est pas autorisée. Les gardes sont gérées de manière automatique.")

    def update(self, request, *args, **kwargs):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("La modification manuelle de garde n'est pas autorisée. Les gardes sont gérées de manière automatique.")

    def partial_update(self, request, *args, **kwargs):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("La modification manuelle de garde n'est pas autorisée. Les gardes sont gérées de manière automatique.")

    def destroy(self, request, *args, **kwargs):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("La suppression manuelle de garde n'est pas autorisée. Les gardes sont gérées de manière automatique.")


class PharmacieAdminSerializer(serializers.ModelSerializer):
    delegation   = DelegationSerializer(read_only=True)
    proprietaire = serializers.SerializerMethodField()

    class Meta:
        model  = Pharmacie
        fields = [
            'id', 'nom', 'adresse', 'telephone', 'email',
            'categorie', 'est_active', 'created_at',
            'delegation', 'proprietaire',
        ]

    def get_proprietaire(self, obj):
        p = obj.proprietaire
        if not p:
            return None
        return {
            'first_name': getattr(p, 'first_name', '') or '',
            'last_name' : getattr(p, 'last_name',  '') or '',
            'email'     : getattr(p, 'email',       '') or '',
            'telephone' : getattr(p, 'telephone',   None),
        }
        
class PharmacieAdminViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PharmacieFilter
    search_fields = ['nom', 'adresse', 'telephone']
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.roles.filter(name='administrateur').exists():
            return Pharmacie.objects.all().select_related(
                'delegation__gouvernorat')
        return Pharmacie.objects.filter(
            proprietaire=user
            ).select_related('delegation__gouvernorat')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PharmacieCreateSerializer
        if self.action == 'retrieve':
            return PharmacieDetailSerializer
        return PharmacieListSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def _est_admin(self, user):
        return (
            user.is_staff or
            user.is_superuser or
            user.roles.filter(name='gérant').exists()
        )

    def perform_create(self, serializer):
        user = self.request.user
        nb_pharmacies = Pharmacie.objects.filter(proprietaire=user).count()
        if nb_pharmacies >= 1:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                "Vous avez déjà une pharmacie enregistrée. "
                "Un utilisateur ne peut en posséder qu'une seule."
            )
        pharmacie = serializer.save(proprietaire=user)
        self._generer_horaires(pharmacie)

    def perform_update(self, serializer):
        pharmacie = self.get_object()
        user = self.request.user

        # Vérification des droits
        if not self._est_admin(user) and str(pharmacie.proprietaire_id) != str(user.id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne pouvez modifier que votre propre pharmacie.")

        ancienne_cat = pharmacie.categorie
        pharmacie_maj = serializer.save()

        if ancienne_cat != pharmacie_maj.categorie:
            pharmacie_maj.horaires_travail.all().delete()
            self._generer_horaires(pharmacie_maj)

    def perform_destroy(self, instance):
        user = self.request.user
        if not (user.is_superuser or user.roles.filter(name='administrateur').exists()) and str(instance.proprietaire_id) != str(user.id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne pouvez supprimer que votre propre pharmacie.")
        instance.delete()

    def _generer_horaires(self, pharmacie):
        aujourd_hui = date.today()
        en_ramadan = PeriodeRamadan.objects.filter(
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
                        'pause_debut': time(13, 0),
                        'pause_fin': time(15, 0),
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

    @action(detail=True, methods=['patch'])
    def toggle_active(self, request, pk=None):
        pharmacie = self.get_object()
        pharmacie.est_active = not pharmacie.est_active
        pharmacie.save()
        return Response({
            'message': f"Pharmacie {'activée' if pharmacie.est_active else 'désactivée'}.",
            'est_active': pharmacie.est_active,
        })

    @action(detail=False, methods=['get'], url_path='peut-creer')
    def peut_creer(self, request):
        nb = Pharmacie.objects.filter(proprietaire=request.user).count()
        if nb >= 1:
            return Response({
                'peut_creer': False,
                'raison': "Vous avez déjà une pharmacie enregistrée. "
                          "Un utilisateur ne peut en posséder qu'une seule."
            })
        return Response({'peut_creer': True, 'raison': None})

# ──────────────────────────────────────────────────────────
# PHARMACIENS DANS UNE PHARMACIE (admin uniquement)
# ──────────────────────────────────────────────────────────

# pharmacies/views.py — remplacer mes_pharmaciens et ajouter un endpoint admin dédié

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_pharmaciens(request):
    if not is_admin(request.user):
        return Response({'detail': 'Accès réservé aux administrateurs.'}, status=403)
    
    pharmacie = get_pharmacie_admin(request.user)
    if not pharmacie:
        return Response({'pharmacie_nom': '', 'pharmaciens': []})

    pharmaciens = User.objects.filter(
        roles__name='pharmacien',
        pharmacies_travail=pharmacie
    ).values('id', 'first_name', 'last_name', 'email', 'telephone', 'is_active', 'date_joined').distinct()

    data = [
        {
            'id'           : str(u['id']),
            'nom'          : f"{u['first_name']} {u['last_name']}".strip() or u['email'],
            'email'        : u['email'],
            'telephone'    : u['telephone'] or '',
            'est_actif'    : u['is_active'],
            'date_creation': u['date_joined'],
        }
        for u in pharmaciens
    ]
    return Response({'pharmacie_nom': pharmacie.nom, 'pharmaciens': data})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_pharmacien(request):
    if not is_admin(request.user):
        return Response({'detail': 'Accès réservé aux administrateurs.'}, status=403)

    pharmacie = get_pharmacie_admin(request.user)
    if not pharmacie:
        return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)

    first_name = request.data.get('first_name', '').strip()
    last_name  = request.data.get('last_name',  '').strip()
    email      = request.data.get('email',      '').strip().lower()

    if not first_name or not last_name or not email:
        return Response(
            {'detail': 'Les champs first_name, last_name et email sont obligatoires.'},
            status=400
        )

    if User.objects.filter(email=email).exists():
        return Response({'email': ['Un compte avec cet email existe déjà.']}, status=400)

    import secrets, string
    password = ''.join(
        secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*')
        for _ in range(14)
    )

    # ✅ Sans username
    user = User.objects.create_user(
        email      = email,
        first_name = first_name,
        last_name  = last_name,
        password   = password,
        is_active  = True,
    )

    role_pharmacien, _ = Role.objects.get_or_create(name='pharmacien')
    user.roles.add(role_pharmacien)

    # ✅ pharmacies_travail au lieu de pharmacies
    user.pharmacies_travail.add(pharmacie)

    _send_credentials_email(user, password)

    return Response(
        {
            'detail'    : f'Compte créé pour {email}.',
            'email'     : email,
            'first_name': first_name,
            'last_name' : last_name,
        },
        status=201
    )
# ──────────────────────────────────────────────────────────
# DEMANDES DE SUSPENSION
# ──────────────────────────────────────────────────────────

def _send_credentials_email(user, password):
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(
            subject     = 'Vos identifiants de connexion – Pharma Platform',
            message     = (
                f'Bonjour {user.get_full_name()},\n\n'
                f'Votre compte pharmacien a été créé.\n'
                f'Email    : {user.email}\n'
                f'Mot de passe : {password}\n\n'
                f'Veuillez changer votre mot de passe après votre première connexion.\n'
            ),
            from_email  = settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass
class DemandesSuspensionViewSet(viewsets.ModelViewSet):
    serializer_class   = DemandesSuspensionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        print("user connecté :", user.email)
        # Administrateur voit tout ; admin ne voit que les siennes
        if user.is_superuser or user.roles.filter(name='administrateur').exists():
            return DemandesSuspension.objects.all()
        return DemandesSuspension.objects.filter(demandeur=user)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser or user.roles.filter(name='administrateur').exists():
            serializer.save(demandeur=user)
            return
        pharmacie = Pharmacie.objects.filter(proprietaire=user).first()
        if not pharmacie:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Vous ne possédez aucune pharmacie.')
        serializer.save(demandeur=self.request.user, pharmacie=pharmacie)

    def update(self, request, *args, **kwargs):
        """Admin peut modifier UNIQUEMENT ses demandes encore en_attente."""
        demande = self.get_object()
        if demande.statut != 'en_attente':
            return Response(
                {'detail': 'Impossible de modifier une demande déjà traitée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if str(demande.demandeur_id) != str(request.user.id) and \
           not (request.user.is_superuser or request.user.roles.filter(name='administrateur').exists()):
            return Response({'detail': 'Accès refusé.'}, status=403)
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Admin peut supprimer UNIQUEMENT ses demandes encore en_attente."""
        demande = self.get_object()
        if demande.statut != 'en_attente':
            return Response(
                {'detail': 'Impossible de supprimer une demande déjà traitée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if str(demande.demandeur_id) != str(request.user.id) and \
           not (request.user.is_superuser or request.user.roles.filter(name='administrateur').exists()):
            return Response({'detail': 'Accès refusé.'}, status=403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], url_path='traiter')
    def traiter(self, request, pk=None):
        """Administrateur approuve ou refuse la demande."""
        from django.utils import timezone
        if not (request.user.is_superuser or
                request.user.roles.filter(name='administrateur').exists()):
            return Response({'detail': 'Accès refusé.'}, status=403)

        demande = self.get_object()
        nouveau_statut = request.data.get('statut')   
        commentaire    = request.data.get('commentaire', '')

        if nouveau_statut not in ('approuvee', 'refusee'):
            return Response({'detail': "statut doit être 'approuvee' ou 'refusee'."}, status=400)

        demande.statut                  = nouveau_statut
        demande.commentaire_superadmin  = commentaire
        demande.traite_par              = request.user
        demande.date_traitement         = timezone.now()
        demande.save()

        if nouveau_statut == 'approuvee':
            demande.pharmacie.est_active = False
            demande.pharmacie.save()

        return Response(DemandesSuspensionSerializer(demande).data)
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_citoyens(request):
    if not is_admin(request.user):
        return Response({'pharmacie_nom': '', 'citoyens': []})

    pharmacie = get_pharmacie_admin(request.user)
    if not pharmacie:
        return Response({'pharmacie_nom': '', 'citoyens': []})

    from reservations.models import Reservation
    from django.db.models import Count, Max, F

    # Optimisation : On fait tout en une seule requête SQL avec jointures et groupement
    try:
        qs = (
            Reservation.objects
            .filter(stock__pharmacie=pharmacie)
            .annotate(
                uid=F('citoyen__id'),
                fn=F('citoyen__first_name'),
                ln=F('citoyen__last_name'),
                em=F('citoyen__email')
            )
            .values('uid', 'fn', 'ln', 'em')
            .annotate(
                total_commandes=Count('id'),
                derniere_visite=Max('created_at'),
            )
            .order_by('-derniere_visite')
        )
        
        data = [
            {
                'id'             : str(row['uid']),
                'nom'            : f"{row['fn']} {row['ln']}".strip() or row['em'],
                'email'          : row['em'],
                'total_commandes': row['total_commandes'],
                'derniere_visite': row['derniere_visite'],
            }
            for row in qs
        ]
    except Exception as e:
        return Response({'error': str(e)}, status=500)

    return Response({'pharmacie_nom': pharmacie.nom, 'citoyens': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_gardes(request):
    # 1. Propriétaire direct
    pharmacie = Pharmacie.objects.filter(
        proprietaire=request.user
    ).first()

    # 2. Pharmacien rattaché (pharmacies_travail)
    if not pharmacie:
        pharmacie = request.user.pharmacies_travail.first()

    # 3. Admin avec rôle 'gérant' (sans être propriétaire)
    if not pharmacie and is_admin(request.user):
        pharmacie = get_pharmacie_admin(request.user)

    if not pharmacie:
        return Response(
            {'detail': 'Aucune pharmacie associée.'},
            status=status.HTTP_404_NOT_FOUND
        )

    gardes = GardePharmacie.objects.filter(
        pharmacie=pharmacie
    ).order_by('date_debut')

    serializer = MesGardesSerializer(gardes, many=True)
    return Response({
        'pharmacie_nom': pharmacie.nom,
        'categorie': pharmacie.categorie,
        'gardes': serializer.data,
    })


@api_view(['GET'])
def jours_feries_annee(request):
    annee = request.query_params.get('annee', date.today().year)
    jours = JourFerieTunisie.objects.filter(date__year=annee).order_by('date')
    serializer = JourFerieSerializer(jours, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def periodes_ramadan(request):
    periodes = PeriodeRamadan.objects.all().order_by('-annee')
    serializer = PeriodeRamadanSerializer(periodes, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    from django.utils import timezone
    from accounts.models import User
    from reservations.models import Reservation
    
    user = request.user
    now = timezone.now()
    this_month = now.replace(day=1)

    # Si c'est un SuperAdmin, on garde les stats globales
    if user.is_superuser or user.roles.filter(name='administrateur').exists():
        return Response({
            'total_utilisateurs': User.objects.count(),
            'nouveaux_ce_mois': User.objects.filter(date_joined__gte=this_month).count(),
            'comptes_en_attente': User.objects.filter(is_active=False).count(),
            'pharmacies_actives': Pharmacie.objects.filter(est_active=True).count(),
            'pharmacies_inactives': Pharmacie.objects.filter(est_active=False).count(),
            'nouvelles_ce_mois': Pharmacie.objects.filter(created_at__gte=this_month).count(),
            'roles': {
                'citoyens': User.objects.filter(roles__name='citoyen').count(),
                'pharmaciens': User.objects.filter(roles__name='pharmacien').count(),
                'administrateurs': User.objects.filter(roles__name='gérant').count(),
            }
        })

    # Sinon, on retourne les stats de SA pharmacie
    pharmacie = get_pharmacie_admin(user)
    if not pharmacie:
        return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)

    # Pharmaciens rattachés
    nb_pharmaciens = User.objects.filter(roles__name='pharmacien', pharmacies_travail=pharmacie).count()
    
    # Citoyens ayant commandé (distinct)
    nb_citoyens = Reservation.objects.filter(stock__pharmacie=pharmacie).values('citoyen').distinct().count()
    
    # Commandes totales
    total_commandes = Reservation.objects.filter(stock__pharmacie=pharmacie).count()

    return Response({
        'nb_pharmaciens': nb_pharmaciens,
        'nb_citoyens': nb_citoyens,
        'total_commandes': total_commandes,
        'pharmacie_nom': pharmacie.nom,
        'est_active': pharmacie.est_active
    })
    
# ─────────────────────────────────────────────────────────
# GET /api/pharmacies/historique-citoyen/{citoyen_id}/
# ─────────────────────────────────────────────────────────
 
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historique_citoyen(request, citoyen_id):
    if not is_admin(request.user):
        return Response({'detail': 'Accès réservé aux administrateurs.'}, status=403)

    pharmacie = get_pharmacie_admin(request.user)
    if not pharmacie:
        return Response({'detail': 'Aucune pharmacie trouvée.'}, status=404)

    try:
        citoyen = User.objects.get(pk=citoyen_id)
    except User.DoesNotExist:
        return Response({'detail': 'Citoyen introuvable.'}, status=404)

    from reservations.models import Reservation

    reservations = (
        Reservation.objects
        .filter(stock__pharmacie=pharmacie, citoyen=citoyen)
        .select_related('medicament', 'stock')
        .order_by('-created_at')
    )

    historique = [
        {
            'id'            : str(r.id),
            'medicament_nom': r.medicament.nom,
            'quantite'      : r.quantite,
            'statut'        : r.statut,
            'date_achat'    : r.created_at,
        }
        for r in reservations
    ]

    return Response({
        'citoyen_nom': f"{citoyen.first_name} {citoyen.last_name}".strip() or citoyen.email,
        'historique' : historique,
    })
    


class JourFerieViewSet(viewsets.ModelViewSet):
    queryset = JourFerieTunisie.objects.all().order_by('date')
    serializer_class = JourFerieSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['date__year', 'type_ferie']


class PeriodeRamadanViewSet(viewsets.ModelViewSet):
    queryset = PeriodeRamadan.objects.all().order_by('-annee')
    serializer_class = PeriodeRamadanSerializer
    permission_classes = [IsAuthenticated]
    
class SuperAdminPharmacieViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint exclusif superadmin :
    - Lister TOUTES les pharmacies avec leurs détails
    - Voir les horaires, gardes, propriétaire
    """
    serializer_class   = PharmacieDetailSerializer
    permission_classes = [IsSuperAdmin]
    pagination_class  = None  # Désactive la pagination pour voir tout d'un coup

    def get_queryset(self):
        return Pharmacie.objects.all().select_related(
            'delegation__gouvernorat', 'proprietaire'
        ).prefetch_related(
            'horaires', 'horaires_ramadan', 'gardes'
        )
        
def get_pharmacie_admin(user):
    """Retourne la pharmacie du user connecté ou None."""
    return Pharmacie.objects.filter(proprietaire=user).select_related(
        'delegation__gouvernorat'
    ).first()
 
 
def is_admin(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.roles.filter(name__in=['gérant', 'administrateur']).exists()
    )
 
class HoraireViewSet(viewsets.ModelViewSet):
    serializer_class = HoraireTravailSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['pharmacie', 'pharmacie__delegation__gouvernorat']
    pagination_class= None

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.roles.filter(name='administrateur').exists():
            return HoraireTravail.objects.all().select_related('pharmacie__delegation__gouvernorat')
        pharmacie = Pharmacie.objects.filter(proprietaire=user).first()
        if not pharmacie:
            return HoraireTravail.objects.none()
        return HoraireTravail.objects.filter(pharmacie=pharmacie)


class HoraireRamadanViewSet(viewsets.ModelViewSet):
    serializer_class = HoraireRamadanSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['pharmacie', 'pharmacie__delegation__gouvernorat']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.roles.filter(name='administrateur').exists():
            return HoraireRamadan.objects.all().select_related('pharmacie__delegation__gouvernorat')
        pharmacie = Pharmacie.objects.filter(proprietaire=user).first()
        if not pharmacie:
            return HoraireRamadan.objects.none()
        return HoraireRamadan.objects.filter(pharmacie=pharmacie)
        