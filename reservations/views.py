from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.db.models import Sum
from django.apps import apps
from datetime import datetime

from stock.models import StockPharmacie
from .models import Reservation
from .serializers import ReservationSerializer, ReservationCreateSerializer


# ── Helpers ───────────────────────────────────────────────────────────────────

def _liberer_expirees():
    """
    Passe en 'expiree' toutes les réservations actives dont le délai est écoulé.
    Le stock n'a jamais été déduit → rien à remettre.
    """
    Reservation.objects.filter(
        statut='active',
        expire_at__lte=timezone.now()
    ).update(statut='expiree')


def _quantite_reservee(stock) -> int:
    """Retourne la quantité réservée (actives non expirées) sur un stock."""
    result = Reservation.objects.filter(
        stock=stock,
        statut='active',
        expire_at__gt=timezone.now()
    ).aggregate(total=Sum('quantite'))
    return result['total'] or 0


# ── Recherche avec médicament ─────────────────────────────────────────────────

class RecherchePharmacieView(APIView):
    """
    GET /api/reservations/recherche/
        ?medicament=doliprane&lat=36.8&lng=10.1&rayon=10
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _liberer_expirees()

        nom_med = request.query_params.get('medicament', '').strip()
        try:
            lat   = float(request.query_params.get('lat',   0))
            lng   = float(request.query_params.get('lng',   0))
            rayon = float(request.query_params.get('rayon', 10))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Paramètres lat/lng/rayon invalides.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not nom_med:
            return Response(
                {'detail': 'Paramètre "medicament" requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Indentation correcte — filtre dans la méthode
        stocks = StockPharmacie.objects.select_related(
            'pharmacie', 'pharmacie__delegation',
            'medicament', 'medicament__categorie'
        ).filter(
            quantite_stock__gt=0,
            pharmacie__est_active=True,
            medicament__nom__icontains=nom_med,   # ← filtré directement ici
        )

        now       = datetime.now()
        resultats = []

        for stock in stocks:
            pharmacie = stock.pharmacie

            dispo = stock.quantite_stock - _quantite_reservee(stock)
            if dispo <= 0:
                continue

            distance = pharmacie.distance_km(lat, lng)
            if distance > rayon:
                continue

            est_ouverte = pharmacie.verifier_ouverture(now.date(), now.time())

            resultats.append({
                'stock_id'          : stock.id,
                'pharmacie_id'      : str(pharmacie.id),
                'pharmacie_nom'     : pharmacie.nom,
                'pharmacie_adresse' : pharmacie.adresse,
                'pharmacie_tel'     : pharmacie.telephone,
                'latitude'          : float(pharmacie.latitude)  if pharmacie.latitude  else None,
                'longitude'         : float(pharmacie.longitude) if pharmacie.longitude else None,
                'delegation'        : pharmacie.delegation.nom   if pharmacie.delegation else '',
                'medicament_id'     : stock.medicament.id,
                'medicament_nom'    : stock.medicament.nom,
                'medicament_dci'    : stock.medicament.dci or '',
                'prix_vente'        : float(stock.prix_vente or stock.medicament.prix_vente),
                'quantite_stock'    : stock.quantite_stock,
                'quantite_dispo'    : dispo,
                'ordonnance_requise': stock.medicament.ordonnance_requise,
                'distance_km'       : round(distance, 2),
                'est_ouverte'       : est_ouverte,
            })

        resultats.sort(key=lambda r: (not r['est_ouverte'], r['distance_km']))
        return Response(resultats)


# ── Pharmacies ouvertes (sans médicament) ─────────────────────────────────────

class PharmaciesOuvertesView(APIView):
    """
    GET /api/reservations/pharmacies-ouvertes/
        ?lat=36.8&lng=10.1&rayon=5

    Retourne toutes les pharmacies actives dans le rayon,
    sans filtrer par médicament (vue par défaut au chargement).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            lat   = float(request.query_params.get('lat',   0))
            lng   = float(request.query_params.get('lng',   0))
            rayon = float(request.query_params.get('rayon', 5))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Paramètres lat/lng/rayon invalides.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Pharmacie = apps.get_model('pharmacies', 'Pharmacie')
        pharmacies = Pharmacie.objects.filter(
            est_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).select_related('delegation')

        now       = datetime.now()
        resultats = []

        for pharmacie in pharmacies:
            distance = pharmacie.distance_km(lat, lng)
            if distance > rayon:
                continue

            est_ouverte = pharmacie.verifier_ouverture(now.date(), now.time())

            resultats.append({
                'stock_id'          : None,
                'pharmacie_id'      : str(pharmacie.id),
                'pharmacie_nom'     : pharmacie.nom,
                'pharmacie_adresse' : pharmacie.adresse,
                'pharmacie_tel'     : pharmacie.telephone,
                'latitude'          : float(pharmacie.latitude),
                'longitude'         : float(pharmacie.longitude),
                'delegation'        : pharmacie.delegation.nom if pharmacie.delegation else '',
                'medicament_id'     : None,
                'medicament_nom'    : '',
                'medicament_dci'    : '',
                'prix_vente'        : None,
                'quantite_stock'    : None,
                'quantite_dispo'    : None,
                'ordonnance_requise': False,
                'distance_km'       : round(distance, 2),
                'est_ouverte'       : est_ouverte,
            })

        resultats.sort(key=lambda r: (not r['est_ouverte'], r['distance_km']))
        return Response(resultats)


# ── Réservations ──────────────────────────────────────────────────────────────

class ReservationListCreateView(APIView):
    """
    GET  /api/reservations/   — Mes réservations actives
    POST /api/reservations/   — Créer une réservation
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _liberer_expirees()
        qs = Reservation.objects.filter(
            citoyen=request.user,
            statut='active',
            expire_at__gt=timezone.now()
        ).select_related('stock__pharmacie', 'medicament')
        return Response(ReservationSerializer(qs, many=True).data)

    def post(self, request):
        _liberer_expirees()

        ser = ReservationCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        stock_id = ser.validated_data['stock_id']
        quantite = ser.validated_data['quantite']

        try:
            stock = StockPharmacie.objects.select_related(
                'pharmacie', 'medicament'
            ).get(id=stock_id)
        except StockPharmacie.DoesNotExist:
            return Response(
                {'detail': 'Stock introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        dispo = stock.quantite_stock - _quantite_reservee(stock)
        if quantite > dispo:
            return Response(
                {'detail': f'Quantité insuffisante. Disponible : {dispo}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reservation = Reservation.objects.create(
            citoyen    = request.user,
            stock      = stock,
            medicament = stock.medicament,
            quantite   = quantite,
        )

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED
        )


class AnnulerReservationView(APIView):
    """POST /api/reservations/<id>/annuler/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            reservation = Reservation.objects.get(pk=pk, citoyen=request.user)
        except Reservation.DoesNotExist:
            return Response(
                {'detail': 'Réservation introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if reservation.statut != 'active':
            return Response(
                {'detail': f'Réservation déjà {reservation.get_statut_display()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reservation.statut = 'annulee'
        reservation.save(update_fields=['statut'])
        return Response({'detail': 'Réservation annulée avec succès.'})


class MarquerRecupereeView(APIView):
    """POST /api/reservations/<id>/recuperee/ — appelé par le pharmacien"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            reservation = Reservation.objects.select_related(
                'stock', 'medicament'
            ).get(pk=pk, statut='active')
        except Reservation.DoesNotExist:
            return Response(
                {'detail': 'Réservation active introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if reservation.est_expiree:
            reservation.statut = 'expiree'
            reservation.save(update_fields=['statut'])
            return Response(
                {'detail': 'Réservation expirée. Le stock est libéré.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stock = reservation.stock

        if stock.quantite_stock < reservation.quantite:
            return Response(
                {'detail': 'Stock insuffisant pour finaliser la récupération.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Déduire le stock réellement ici (récupération physique)
        stock.quantite_stock -= reservation.quantite
        stock.save(update_fields=['quantite_stock'])

        med = reservation.medicament
        med.quantite_stock = max(0, med.quantite_stock - reservation.quantite)
        med.save(update_fields=['quantite_stock'])

        reservation.statut = 'recuperee'
        reservation.save(update_fields=['statut'])

        return Response({'detail': 'Récupération confirmée. Stock mis à jour.'})