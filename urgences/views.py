from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.apps import apps

from pharmacies.models import Pharmacie

from .models import DemandeUrgente
from .serializers import DemandeUrgenteSerializer, DemandeUrgenteCreateSerializer


def _expirer_demandes():
    DemandeUrgente.objects.filter(
        statut='en_attente',
        expire_at__lte=timezone.now()
    ).update(statut='expiree')


class DemandeUrgenteListCreateView(APIView):
    """
    GET  /api/urgences/        — Mes demandes
    POST /api/urgences/        — Créer une demande
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _expirer_demandes()
        qs = DemandeUrgente.objects.filter(
            citoyen=request.user
        ).order_by('-created_at')
        return Response(DemandeUrgenteSerializer(qs, many=True).data)

    def post(self, request):
        ser = DemandeUrgenteCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        demande = DemandeUrgente.objects.create(
            citoyen      = request.user,
            type_demande = ser.validated_data['type_demande'],
            titre        = ser.validated_data['titre'],
            description  = ser.validated_data.get('description', ''),
            lat          = ser.validated_data['lat'],
            lng          = ser.validated_data['lng'],
            rayon_km     = ser.validated_data.get('rayon_km', 10),
        )
        return Response(DemandeUrgenteSerializer(demande).data, status=status.HTTP_201_CREATED)


class DemandeUrgenteProchesView(APIView):
    """
    GET /api/urgences/proches/?lat=&lng=&rayon=
    Pharmacien : voir toutes les demandes urgentes proches en attente
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _expirer_demandes()
        try:
            lat   = float(request.query_params.get('lat',   0))
            lng   = float(request.query_params.get('lng',   0))
            rayon = float(request.query_params.get('rayon', 10))
        except (ValueError, TypeError):
            return Response({'detail': 'Paramètres invalides.'}, status=400)

        demandes = DemandeUrgente.objects.filter(
            statut='en_attente',
            expire_at__gt=timezone.now()
        ).select_related('citoyen')

        resultats = []
        for d in demandes:
            if d.lat is None or d.lng is None:
                continue

            import math
            dlat = math.radians(float(d.lat) - lat)
            dlng = math.radians(float(d.lng) - lng)
            a = (math.sin(dlat/2)**2
                 + math.cos(math.radians(lat))
                 * math.cos(math.radians(float(d.lat)))
                 * math.sin(dlng/2)**2)
            dist = 6371 * 2 * math.asin(math.sqrt(a))

            if dist <= rayon:
                data = DemandeUrgenteSerializer(d).data
                data['distance_km'] = round(dist, 2)
                resultats.append(data)

        resultats.sort(key=lambda x: x['distance_km'])
        return Response(resultats)


class RepondreDemandeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            demande = DemandeUrgente.objects.get(pk=pk, statut='en_attente')
        except DemandeUrgente.DoesNotExist:
            return Response(
                {'detail': 'Demande introuvable ou déjà traitée.'},
                status=404
            )

        action = request.data.get('action')
        if action not in ('accepter', 'refuser'):
            return Response({'detail': 'Action invalide.'}, status=400)

        if demande.est_expiree:
            demande.statut = 'expiree'
            demande.save(update_fields=['statut'])
            return Response({'detail': 'Demande expirée.'}, status=400)

        # ── Statut ────────────────────────────────────────────────────────────
        demande.statut = 'acceptee' if action == 'accepter' else 'refusee'

        # ── Assigner la pharmacie du pharmacien connecté ──────────────────────
        pharmacie = Pharmacie.objects.filter(proprietaire=request.user).first()
        if not pharmacie:
            try:
                pharmacie = request.user.pharmacies_travail.first()
            except Exception:
                pharmacie = None

        demande.pharmacie = pharmacie

        # ── SAVE (manquait dans la version précédente → 500) ──────────────────
        demande.save(update_fields=['statut', 'pharmacie'])

        return Response(DemandeUrgenteSerializer(demande).data)


class AnnulerDemandeView(APIView):
    """POST /api/urgences/<id>/annuler/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            demande = DemandeUrgente.objects.get(pk=pk, citoyen=request.user)
        except DemandeUrgente.DoesNotExist:
            return Response({'detail': 'Demande introuvable.'}, status=404)

        if demande.statut != 'en_attente':
            return Response(
                {'detail': f'Demande déjà {demande.statut}.'},
                status=400
            )

        demande.statut = 'refusee'
        demande.save(update_fields=['statut'])
        return Response({'detail': 'Demande annulée.'})


class HistoriquePharmacienView(APIView):
    """GET /api/urgences/historique/ — Demandes traitées par cette pharmacie"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacie = Pharmacie.objects.filter(proprietaire=request.user).first()
        if not pharmacie:
            try:
                pharmacie = request.user.pharmacies_travail.first()
            except Exception:
                pharmacie = None
        if not pharmacie:
            return Response({'detail': 'Pharmacie introuvable.'}, status=404)

        qs = DemandeUrgente.objects.filter(
            pharmacie=pharmacie
        ).order_by('-created_at')

        return Response(DemandeUrgenteSerializer(qs, many=True).data)