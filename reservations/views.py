from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.db.models import Sum
from django.apps import apps
from datetime import datetime
import logging

from stock.models import StockPharmacie
from .models import Reservation
from .serializers import ReservationSerializer, ReservationCreateSerializer

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _liberer_expirees():
    Reservation.objects.filter(
        statut='active',
        expire_at__lte=timezone.now()
    ).update(statut='expiree')


def _quantite_reservee(stock) -> int:
    result = Reservation.objects.filter(
        stock=stock,
        statut='active',
        expire_at__gt=timezone.now()
    ).aggregate(total=Sum('quantite'))
    return result['total'] or 0


# ── Recherche avec médicament ─────────────────────────────────────────────────

class RecherchePharmacieView(APIView):
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
                {'detail': 'Parametres lat/lng/rayon invalides.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not nom_med:
            return Response(
                {'detail': 'Parametre "medicament" requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stocks = StockPharmacie.objects.select_related(
            'pharmacie', 'pharmacie__delegation',
            'medicament', 'medicament__categorie'
        ).filter(
            quantite_stock__gt=0,
            pharmacie__est_active=True,
            medicament__nom__icontains=nom_med,
        )

        now       = datetime.now()
        resultats = []

        for stock in stocks:
            pharmacie = stock.pharmacie
            dispo     = stock.quantite_stock - _quantite_reservee(stock)
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
                'prix_vente'        : float(stock.prix_vente) if stock.prix_vente and  float (stock.prix_vente) > 0 else float(stock.medicament.prix_vente),
                'quantite_stock'    : stock.quantite_stock,
                'quantite_dispo'    : dispo,
                'ordonnance_requise': stock.medicament.ordonnance_requise,
                'distance_km'       : round(distance, 2),
                'est_ouverte'       : est_ouverte,
            })

        resultats.sort(key=lambda r: (not r['est_ouverte'], r['distance_km']))
        return Response(resultats)


# ── Pharmacies ouvertes ───────────────────────────────────────────────────────

class PharmaciesOuvertesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            lat   = float(request.query_params.get('lat',   0))
            lng   = float(request.query_params.get('lng',   0))
            rayon = float(request.query_params.get('rayon', 5))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Parametres lat/lng/rayon invalides.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Pharmacie  = apps.get_model('pharmacies', 'Pharmacie')
        pharmacies = Pharmacie.objects.filter(
            est_active        = True,
            latitude__isnull  = False,
            longitude__isnull = False,
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _liberer_expirees()
        qs = Reservation.objects.filter(
            citoyen       = request.user,
            statut        = 'active',
            expire_at__gt = timezone.now()
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
                'pharmacie', 'medicament', 'pharmacie__proprietaire'
            ).get(id=stock_id)
        except StockPharmacie.DoesNotExist:
            return Response(
                {'detail': 'Stock introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        dispo = stock.quantite_stock - _quantite_reservee(stock)
        if quantite > dispo:
            return Response(
                {'detail': f'Quantite insuffisante. Disponible : {dispo}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reservation = Reservation.objects.create(
            citoyen    = request.user,
            stock      = stock,
            medicament = stock.medicament,
            quantite   = quantite,
            statut     = 'active',
        )

        dispo_apres = stock.quantite_stock - _quantite_reservee(stock)
        if dispo_apres <= 0 or dispo_apres <= stock.seuil_alerte:
            try:
                from stock.sms_service import verifier_et_notifier_stock_virtuel
                verifier_et_notifier_stock_virtuel(stock, quantite_virtuelle=dispo_apres)
            except Exception as e:
                logger.error(f"Erreur notification stock faible/rupture après reservation : {e}")

        # ── Notification au CITOYEN ───────────────────────────
        try:
            from .sms_service import notifier_reservation_confirmee
            notifier_reservation_confirmee(
                citoyen_id     = request.user.pk,
                pharmacie_nom  = stock.pharmacie.nom,
                medicament_nom = stock.medicament.nom,
                quantite       = quantite,
                expire_at      = reservation.expire_at,
                citoyen_prenom = request.user.first_name,
            )
        except Exception as e:
            logger.error(f"Erreur notification citoyen : {e}", exc_info=True)

        # ── Notification au PHARMACIEN ────────────────────────
        try:
            from .sms_service import notifier_nouvelle_reservation_pharmacien
            pharmacien  = stock.pharmacie.proprietaire
            citoyen_nom = (
                f"{request.user.first_name} {request.user.last_name}".strip()
                or request.user.email
            )
            notifier_nouvelle_reservation_pharmacien(
                pharmacien_id  = pharmacien.pk,
                citoyen_nom    = citoyen_nom,
                medicament_nom = stock.medicament.nom,
                quantite       = quantite,
                pharmacie_nom  = stock.pharmacie.nom,
                expire_at      = reservation.expire_at,
            )
        except Exception as e:
            logger.error(f"Erreur notification pharmacien : {e}")

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED
        )


# ── Annulation ────────────────────────────────────────────────────────────────

class AnnulerReservationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            reservation = Reservation.objects.select_related(
                'stock__pharmacie', 'medicament', 'citoyen'
            ).get(pk=pk, citoyen=request.user)
        except Reservation.DoesNotExist:
            return Response(
                {'detail': 'Reservation introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if reservation.statut != 'active':
            return Response(
                {'detail': f'Reservation deja {reservation.get_statut_display()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reservation.statut = 'annulee'
        reservation.save(update_fields=['statut'])

        # ── Notification annulation ───────────────────────────
        try:
            from .sms_service import notifier_reservation_annulee
            notifier_reservation_annulee(
                citoyen_id     = reservation.citoyen.pk,
                medicament_nom = reservation.medicament.nom,
                pharmacie_nom  = reservation.stock.pharmacie.nom,
                citoyen_prenom = reservation.citoyen.first_name,
            )
        except Exception as e:
            logger.error(f"Erreur notification annulation : {e}")

        return Response({'detail': 'Reservation annulee avec succes.'})


# ── Récupération ──────────────────────────────────────────────────────────────

class MarquerRecupereeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            reservation = Reservation.objects.select_related(
                'stock', 'stock__pharmacie', 'medicament', 'citoyen'
            ).get(pk=pk, statut='active')
        except Reservation.DoesNotExist:
            return Response(
                {'detail': 'Reservation active introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if reservation.est_expiree:
            reservation.statut = 'expiree'
            reservation.save(update_fields=['statut'])
            return Response(
                {'detail': 'Reservation expiree. Le stock est libere.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stock = reservation.stock

        if stock.quantite_stock < reservation.quantite:
            return Response(
                {'detail': 'Stock insuffisant pour finaliser la recuperation.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Mise à jour stocks ────────────────────────────────
        stock.quantite_stock -= reservation.quantite
        stock.save(update_fields=['quantite_stock'])

        med = reservation.medicament
        med.quantite_stock = max(0, med.quantite_stock - reservation.quantite)
        med.save(update_fields=['quantite_stock'])

        # ── NOUVEAU : Alerte stock faible / rupture vers le pharmacien ──
        try:
            from stock.sms_service import verifier_et_notifier_stock
            stock.refresh_from_db()
            verifier_et_notifier_stock(stock)
        except Exception as e:
            logger.error(f"[Reservation #{pk}] Erreur alerte stock après récupération : {e}")

        # ── Marquer récupérée ─────────────────────────────────
        reservation.statut = 'recuperee'
        reservation.save(update_fields=['statut'])

        # ── Créer la vente automatiquement ───────────────────
        citoyen_nom = ''
        try:
            from stock.models import Vente, LigneVente

            pharmacie     = stock.pharmacie
            pharmacien    = pharmacie.proprietaire
          
            quantite = reservation.quantite

            # Récupérer le prix correctement (None check explicite, pas "or")
            prix_unitaire = None
            if getattr(stock, "prix_vente", None) is not None and float(stock.prix_vente) > 0:
                prix_unitaire = float(stock.prix_vente)
            elif getattr(med, "prix_vente", None) is not None and float(med.prix_vente) > 0:
                prix_unitaire = float(med.prix_vente)
            else:
                prix_unitaire = 0.0
                logger.warning(
                    f"[Reservation #{pk}] Prix introuvable pour stock #{stock.id} "
                    f"({med.nom}) — vente créée avec total 0."
                )

            total_vente = round(prix_unitaire * quantite, 3)

            if reservation.citoyen:
                citoyen_nom = (
                    f"{reservation.citoyen.first_name} {reservation.citoyen.last_name}".strip()
                    or reservation.citoyen.email
                )
            else:
                citoyen_nom = ""

            vente = Vente.objects.create(
                pharmacie=pharmacie,
                created_by=pharmacien,
                note=f"Reservation #{reservation.id} — {citoyen_nom}",
                total=total_vente,  # ← total calculé directement, pas de double save
            )
            LigneVente.objects.create(
                vente=vente,
                medicament=med,
                quantite=quantite,
                prix_unitaire=prix_unitaire,
            )
            logger.info(
                f"[Reservation #{pk}] Vente #{vente.id} — "
                f"{quantite}x {med.nom} à {prix_unitaire} DT = {total_vente} DT"
            )

        except Exception as e:
            logger.error(f"[Reservation #{pk}] Erreur creation vente automatique : {e}")

        try:
            from stock.models import Notification

            tel_citoyen = getattr(reservation.citoyen, 'telephone', '') if reservation.citoyen else ''
            message_notif = (
                f"Le citoyen {citoyen_nom or 'inconnu'} a récupéré "
                f"{reservation.quantite}x {reservation.medicament.nom}."
            )

            Notification.objects.create(
                pharmacie    = stock.pharmacie,
                medicament   = reservation.medicament,
                type         = 'reservation_recuperee',
                message      = message_notif,
                statut       = 'envoye',
                destinataire = tel_citoyen,
            )
            logger.info(f"[Reservation #{pk}] Notification BDD créée (reservation_recuperee).")
        except Exception as e:
            logger.error(f"[Reservation #{pk}] Erreur création notification BDD récupération : {e}")

        # ── Notification récupération au citoyen ─────────────
        try:
            if reservation.citoyen:
                from .sms_service import notifier_reservation_recuperee
                notifier_reservation_recuperee(
                    citoyen_id     = reservation.citoyen.pk,
                    medicament_nom = reservation.medicament.nom,
                    quantite       = reservation.quantite,
                    pharmacie_nom  = reservation.stock.pharmacie.nom,
                    citoyen_prenom = reservation.citoyen.first_name,
                )
        except Exception as e:
            logger.error(f"Erreur notification récupération : {e}")

        return Response({'detail': 'Recuperation confirmee. Stock mis a jour.'})


# ── Pharmacien — voir ses réservations ───────────────────────────────────────

class PharmacienReservationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from pharmacies.models import Pharmacie
        pharmacie = Pharmacie.objects.filter(proprietaire=request.user).first()
         
         
        if not pharmacie:
            pharmacie = request.user.pharmacies_travail.first()  # Tentative de fallback si relation directe non trouvée

        if not pharmacie:
            return Response(
                {'detail': 'Acces reserve aux pharmaciens.'},
                status=status.HTTP_403_FORBIDDEN
            )

        reservations = Reservation.objects.filter(
            stock__pharmacie=pharmacie
        ).select_related('stock__pharmacie', 'medicament', 'citoyen')

        return Response(ReservationSerializer(reservations, many=True).data)

# ── Historique citoyen ────────────────────────────────────────────────────────

class HistoriqueReservationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _liberer_expirees()
        qs = Reservation.objects.filter(
            citoyen=request.user
        ).select_related('stock__pharmacie', 'medicament').order_by('-created_at')
        return Response(ReservationSerializer(qs, many=True).data)
    

class HistoriqueReservationsProprietaireView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from pharmacies.models import Pharmacie

        # Récupérer la pharmacie du propriétaire
        pharmacie = Pharmacie.objects.filter(proprietaire=request.user).first()
        if not pharmacie:
            return Response(
                {'detail': 'Accès réservé au propriétaire.'},
                status=status.HTTP_403_FORBIDDEN
            )

        qs = Reservation.objects.filter(
            stock__pharmacie=pharmacie
        ).select_related('stock__pharmacie', 'medicament', 'citoyen')

        # ── Filtre par date ───────────────────────────────────
        date_debut = request.query_params.get('date_debut')
        date_fin   = request.query_params.get('date_fin')
        if date_debut:
            qs = qs.filter(created_at__date__gte=date_debut)
        if date_fin:
            qs = qs.filter(created_at__date__lte=date_fin)

        # ── Filtre par citoyen (nom ou email) ─────────────────
        """citoyen_q = request.query_params.get('citoyen', '').strip()
        if citoyen_q:
            qs = qs.filter(
                models.Q(citoyen__first_name__icontains=citoyen_q) |
                models.Q(citoyen__last_name__icontains=citoyen_q)  |
                models.Q(citoyen__email__icontains=citoyen_q)
            )"""

        from django.db.models import Q
        citoyen_q = request.query_params.get("citoyen", "").strip()
        if citoyen_q:
            qs = qs.filter(
                Q(citoyen__first_name__icontains=citoyen_q) |
                Q(citoyen__last_name__icontains=citoyen_q)  |
                Q(citoyen__email__icontains=citoyen_q)              
                )


        # ── Filtre par statut ─────────────────────────────────
        statut = request.query_params.get('statut', '').strip()
        if statut:
            qs = qs.filter(statut=statut)

        qs = qs.order_by('-created_at')
        return Response(ReservationSerializer(qs, many=True).data)