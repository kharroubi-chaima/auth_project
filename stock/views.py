from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import F, IntegerField
from datetime import date, timedelta
import logging

from .models import (
    Medicament,
    Categorie,
    MouvementStock,
    Notification,
    StockPharmacie,
    Vente,
    ATC,
)
from .serializers import (
    MedicamentSerializer,
    CategorieSerializer,
    MouvementStockSerializer,
    StockPharmacieSerializer,
    VenteSerializer,
    NotificationSerializer,
    ATCSerializer,
)
from .permissions import IsAdminRole
from .prediction_service import StockPredictionService

logger = logging.getLogger(__name__)


# ── Helper global ─────────────────────────────────────────────────────────────


def get_pharmacie_user(user):
    from pharmacies.models import Pharmacie

    # Cas 1 : propriétaire/admin
    pharmacie = Pharmacie.objects.filter(proprietaire=user).first()
    if pharmacie:
        return pharmacie

    # Cas 2 : pharmacien employé
    pharmacie = user.pharmacies_travail.first()

    if pharmacie:
        return pharmacie

    return None


# ── Catégories ────────────────────────────────────────────────────────────────


class CategorieViewSet(viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    permission_classes = [IsAuthenticated]


# ── Médicaments ───────────────────────────────────────────────────────────────


class MedicamentViewSet(viewsets.ModelViewSet):
    serializer_class = MedicamentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["categorie", "ordonnance_requise"]
    search_fields = ["nom", "dci"]
    ordering_fields = ["nom", "prix_vente", "date_expiration", "quantite_stock"]

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        """
        ✅ CORRIGÉ : filtre les médicaments selon la pharmacie de l'user
        """
        from django.db.models import OuterRef, Subquery, IntegerField
        base_qs = Medicament.objects.select_related("categorie").all()
        user = self.request.user

        # 1. SuperAdmin (Plateforme) : voit tout le catalogue global
        if user.is_superuser or user.roles.filter(name="administrateur").exists():
            return base_qs

        # 2. Admin de pharmacie ou Pharmacien : voit uniquement ce qui est dans SA pharmacie
        pharmacie = get_pharmacie_user(user)
        if not pharmacie:
            return base_qs.none()

        stock_qs = StockPharmacie.objects.filter(
            pharmacie=pharmacie,
            medicament=OuterRef("pk")
        ).values("quantite_stock")[:1]
        
        return base_qs.filter(
            stocks__pharmacie=pharmacie
        ).annotate(
            quantite_stock_reel=Subquery(stock_qs, output_field=IntegerField())
        ).distinct()
        
        
    @action(detail=False, methods=["get"], url_path="expirent-bientot")
    def expirent_bientot(self, request):
        qs = self.get_queryset().filter(
            date_expiration__lte=date.today() + timedelta(days=30)
        )
        return Response(MedicamentSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="stock-faible")
    def stock_faible(self, request):
        qs = self.get_queryset().filter(quantite_stock__lte=F("seuil_alerte"))
        return Response(MedicamentSerializer(qs, many=True).data)

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        import csv
        import io
        from decimal import Decimal
        from django.db import transaction

        user = request.user
        pharmacie = get_pharmacie_user(user)

        if not self._est_admin() and not pharmacie:
            raise PermissionDenied("Aucune pharmacie associée à votre compte.")

        csv_file = request.FILES.get("file")
        if not csv_file:
            return Response({"error": "Veuillez fournir un fichier CSV."}, status=400)

        try:
            file_data = csv_file.read().decode("utf-8")
            io_string = io.StringIO(file_data)
            reader = csv.DictReader(io_string)
        except Exception as e:
            return Response({"error": f"Erreur lors de la lecture du fichier : {str(e)}"}, status=400)

        imported_count = 0
        errors = []

        with transaction.atomic():
            for row_idx, row in enumerate(reader, start=1):
                try:
                    nom = row.get("nom", "").strip()
                    if not nom:
                        errors.append(f"Ligne {row_idx} : Le nom du médicament est obligatoire.")
                        continue

                    dci = row.get("dci", "").strip() or None
                    atc_nom = row.get("atc", "").strip()
                    cat_nom = row.get("categorie", "").strip()

                    atc_obj = None
                    if atc_nom:
                        atc_obj, _ = ATC.objects.get_or_create(nom=atc_nom)

                    cat_obj = None
                    if cat_nom:
                        cat_obj, _ = Categorie.objects.get_or_create(
                            nom=cat_nom,
                            defaults={"atc": atc_obj}
                        )

                    try:
                        prix_achat = Decimal(row.get("prix_achat", "0") or "0")
                    except Exception:
                        prix_achat = Decimal("0")

                    try:
                        prix_vente = Decimal(row.get("prix_vente", "0") or "0")
                    except Exception:
                        prix_vente = Decimal("0")

                    date_exp_str = row.get("date_expiration", "").strip()
                    date_expiration = None
                    if date_exp_str:
                        try:
                            date_expiration = date.fromisoformat(date_exp_str)
                        except ValueError:
                            errors.append(f"Ligne {row_idx} : Format de date d'expiration invalide ({date_exp_str}). Attendu : AAAA-MM-JJ.")
                            continue

                    ordonnance_requise = row.get("ordonnance_requise", "").strip().lower() in ["true", "1", "yes", "oui"]
                    description = row.get("description", "").strip() or None

                    try:
                        quantite_stock = int(row.get("quantite_stock", "0") or "0")
                    except ValueError:
                        quantite_stock = 0

                    try:
                        seuil_alerte = int(row.get("seuil_alerte", "10") or "10")
                    except ValueError:
                        seuil_alerte = 10

                    medicament = Medicament.objects.filter(nom__iexact=nom).first()
                    created = False
                    if not medicament:
                        medicament = Medicament.objects.create(
                            nom=nom,
                            dci=dci,
                            categorie=cat_obj,
                            prix_achat=prix_achat,
                            prix_vente=prix_vente,
                            date_expiration=date_expiration,
                            ordonnance_requise=ordonnance_requise,
                            description=description,
                            quantite_stock=quantite_stock,
                            seuil_alerte=seuil_alerte,
                        )
                        created = True
                    else:
                        medicament.dci = dci or medicament.dci
                        medicament.categorie = cat_obj or medicament.categorie
                        medicament.prix_achat = prix_achat or medicament.prix_achat
                        medicament.prix_vente = prix_vente or medicament.prix_vente
                        medicament.date_expiration = date_expiration or medicament.date_expiration
                        medicament.ordonnance_requise = ordonnance_requise
                        medicament.description = description or medicament.description
                        medicament.quantite_stock += quantite_stock
                        medicament.save()

                    if pharmacie:
                        stock, stock_created = StockPharmacie.objects.get_or_create(
                            pharmacie=pharmacie,
                            medicament=medicament,
                            defaults={
                                "quantite_stock": quantite_stock,
                                "seuil_alerte": seuil_alerte,
                                "prix_vente": prix_vente,
                            }
                        )
                        if not stock_created:
                            stock.quantite_stock += quantite_stock
                            stock.save()

                        # Vérifier le seuil et pousser la notification via WebSocket
                        from .sms_service import verifier_et_notifier_stock
                        verifier_et_notifier_stock(stock)

                    imported_count += 1

                except Exception as ex:
                    errors.append(f"Ligne {row_idx} : Erreur inattendue : {str(ex)}")

            if errors:
                transaction.set_rollback(True)
                return Response({"errors": errors}, status=400)

        return Response({
            "message": f"Importation réussie de {imported_count} médicaments.",
            "imported_count": imported_count
        })

    def perform_create(self, serializer):
        user = self.request.user
        pharmacie = get_pharmacie_user(user)

        if not self._est_admin() and not pharmacie:
            raise PermissionDenied("Aucune pharmacie associée à votre compte.")

        quantite_initiale = self.request.data.get("quantite_stock", 0)
        try:
            quantite_initiale = int(quantite_initiale)
        except (ValueError, TypeError):
            quantite_initiale = 0

        medicament = serializer.save(quantite_stock=quantite_initiale)

        if pharmacie:
            stock, created = StockPharmacie.objects.get_or_create(
                pharmacie=pharmacie,
                medicament=medicament,
                defaults={
                    "quantite_stock": quantite_initiale,
                    "seuil_alerte": medicament.seuil_alerte,
                    "prix_vente": medicament.prix_vente,
                },
            )
            from .sms_service import verifier_et_notifier_stock

            verifier_et_notifier_stock(stock)

    def perform_update(self, serializer):
        nouvelle_quantite = self.request.data.get("quantite_stock")
        medicament = serializer.save()
        pharmacie = get_pharmacie_user(self.request.user)
        
        if pharmacie:
            update_data = {
                'prix_vente'  : medicament.prix_vente,
                'seuil_alerte': medicament.seuil_alerte,
            }
            if nouvelle_quantite is not None:
                update_data['quantite_stock'] = int(nouvelle_quantite)
                
                medicament.quantite_stock = int(nouvelle_quantite)
                medicament.save(update_fields=['quantite_stock'])

            stock_qs = StockPharmacie.objects.filter(
                pharmacie=pharmacie,
                medicament=medicament,
            )
            stock_qs.update(**update_data)
            stock = stock_qs.select_related(
                "pharmacie__proprietaire", "medicament"
            ).first()
            if stock:
                from .sms_service import verifier_et_notifier_stock
                verifier_et_notifier_stock(stock)


# ── Stock par pharmacie ───────────────────────────────────────────────────────


class StockPharmacieViewSet(viewsets.ModelViewSet):
    serializer_class = StockPharmacieSerializer
    permission_classes = [IsAuthenticated]

    pagination_class = None  # désactive pagination pour les listes complètes
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["pharmacie", "medicament", "medicament__categorie"]
    search_fields = ["medicament__nom", "medicament__dci"]
    ordering_fields = ["medicament__nom"]

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        base_qs = StockPharmacie.objects.select_related(
            "pharmacie", "medicament", "medicament__categorie"
        )
        user = self.request.user
        
        # 1. SuperAdmin (Plateforme) : voit tout
        if user.is_superuser or user.roles.filter(name="administrateur").exists():
            return base_qs.all()

        # 2. Admin de pharmacie ou Pharmacien : voit uniquement sa pharmacie
        pharmacie = get_pharmacie_user(user)
        if pharmacie:
            return base_qs.filter(pharmacie=pharmacie)
            
        return base_qs.none()

    @action(detail=False, methods=["get"], url_path="alertes")
    def alertes(self, request):
        try:
            qs = self.get_queryset()

            # Filtre par pharmacie
            pharmacie_id = request.query_params.get("pharmacie")
            if pharmacie_id:
                qs = qs.filter(pharmacie_id=pharmacie_id)

            # filter par med
            search = request.query_params.get("search", "")
            if search:
                qs = qs.filter(medicament__nom__icontains=search) | qs.filter(
                    medicament__dci__icontains=search
                )

            stock_faible = qs.filter(quantite_stock__lte=F("seuil_alerte"))
            date_limite = date.today() + timedelta(days=30)
            expire_bientot = qs.filter(medicament__date_expiration__lte=date_limite)
            rupture_stock = qs.filter(quantite_stock=0)

            return Response(
                {
                    "stock_faible": StockPharmacieSerializer(
                        stock_faible, many=True
                    ).data,
                    "expire_bientot": StockPharmacieSerializer(
                        expire_bientot, many=True
                    ).data,
                    "rupture_stock": StockPharmacieSerializer(
                        rupture_stock, many=True
                    ).data,
                    "stats": {
                        "total_produits": qs.count(),
                        "stock_faible": stock_faible.count(),
                        "expire_bientot": expire_bientot.count(),
                        "rupture_stock": rupture_stock.count(),
                    },
                }
            )

        except Exception as e:
            logger.error(f"Erreur alertes: {e}", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=["get"], url_path="prediction-rupture")
    def prediction_rupture(self, request, pk=None):
        """
        Action pour prédire la date de rupture de stock d'un produit spécifique.
        """
        stock = self.get_object()
        result = StockPredictionService.predict_stockout(stock.medicament_id, stock.pharmacie_id)
        
        if "error" in result:
            return Response({"detail": result["error"]}, status=400)
            
        return Response({
            "stock_id": pk,
            "estimated_date": result["stockout_date"],
            "message": f"Rupture prévue aux alentours du {result['stockout_date']}.",
            "days_until": result["days_until_stockout"]
        })

    @action(detail=False, methods=["get"], url_path="predictions-globales")
    def predictions_globales(self, request):
        """
        Action pour prédire la date de rupture de stock pour tous les stocks critiques.
        """
        user = self.request.user
        pharmacie = get_pharmacie_user(user)
        
        # Si c'est un SuperAdmin sans pharmacie, pharmacie_id = None
        pharmacie_id = pharmacie.id if pharmacie else None
        
        predictions = StockPredictionService.get_critical_predictions(pharmacie_id)
        
        return Response({
            "predictions": predictions
        })

    @action(detail=True, methods=["get"], url_path="historique")
    def historique(self, request, pk=None):
        stock = self.get_object()
        mouvements = stock.mouvements.select_related("created_by").all()
        return Response(MouvementStockSerializer(mouvements, many=True).data)

    # ── Mouvements ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="alertes-globales")
    def alertes_globales(self, request):
        user = request.user
        if not (user.is_superuser or user.roles.filter(name="administrateur").exists()):
            return Response({"error": "Permission denied"}, status=403)
        from pharmacies.models import Pharmacie

        pharmacies = Pharmacie.objects.filter(est_active=True).order_by("nom")
        date_limite = date.today() + timedelta(days=30)
        result = []
        for pharmacie in pharmacies:
            qs = StockPharmacie.objects.filter(pharmacie=pharmacie).select_related(
                "medicament"
            )
            stock_faible = qs.filter(
                quantite_stock__gte=0, quantite_stock__lte=F("seuil_alerte")
            )
            expire_bientot = qs.filter(medicament__date_expiration__lte=date_limite)
            rupture_stock = qs.filter(quantite_stock=0)
            if not (
                stock_faible.exists()
                or expire_bientot.exists()
                or rupture_stock.exists()
            ):
                continue

            result.append(
                {
                    "pharmacie_id": pharmacie.id,
                    "pharmacie_nom": pharmacie.nom,
                    "categorie": pharmacie.categorie,
                    "stats": {
                        "total_produits": qs.count(),
                        "stock_faible": stock_faible.count(),
                        "expire_bientot": expire_bientot.count(),
                        "rupture_stock": rupture_stock.count(),
                    },
                    "stock_faible": StockPharmacieSerializer(
                        stock_faible, many=True
                    ).data,
                    "expire_bientot": StockPharmacieSerializer(
                        expire_bientot, many=True
                    ).data,
                    "rupture_stock": StockPharmacieSerializer(
                        rupture_stock, many=True
                    ).data,
                }
            )
        return Response({"total_pharmacies_alertes": len(result), "pharmacies": result})

    @action(detail=False, methods=["get"], url_path="top-consomme")
    def top_consomme(self, request):

        from django.db.models import Sum
        from .models import LigneVente

        user = request.user
        pharmacie_id = request.query_params.get("pharmacie")
        qs = LigneVente.objects.select_related("medicament", "vente__pharmacie")

        if user.is_superuser or user.roles.filter(name="administrateur").exists():
            if pharmacie_id:
                qs = qs.filter(vente__pharmacie_id=pharmacie_id)

        else:
            pharmacie = get_pharmacie_user(user)
            if not pharmacie:
                return Response(
                    {"detail": "Aucune pharmacie associée à votre compte."}, status=403
                )
            qs = qs.filter(vente__pharmacie__in=pharmacie)
        top = (
            qs.values("medicament__id", "medicament__nom")
            .annotate(total_vendu=Sum("quantite"))
            .order_by("-total_vendu")
            .first()
        )
        if not top:
            return Response(None)
        return Response(
            {
                "medicament_id": top["medicament__id"],
                "medicament_nom": top["medicament__nom"],
                "total_vendu": top["total_vendu"],
            }
        )


class MouvementStockViewSet(viewsets.ModelViewSet):
    serializer_class = MouvementStockSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["stock", "stock__pharmacie", "stock__medicament", "type"]
    http_method_names = ["get", "post"]
    queryset = MouvementStock.objects.all()

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        base_qs = MouvementStock.objects.select_related(
            "stock__medicament", "stock__pharmacie", "created_by"
        )
        if self._est_admin():
            return base_qs.all()

        # ✅ CORRIGÉ
        pharmacie = get_pharmacie_user(self.request.user)
        if pharmacie:
            return base_qs.filter(stock__pharmacie=pharmacie)
        return base_qs.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── Ventes ────────────────────────────────────────────────────────────────────


class VenteViewSet(viewsets.ModelViewSet):
    serializer_class = VenteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["pharmacie"]
    ordering_fields = ["created_at", "total"]
    http_method_names = ["get", "post"]

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        base_qs = Vente.objects.prefetch_related("lignes__medicament").select_related(
            "pharmacie", "created_by"
        )
        user = self.request.user

        # 1. SuperAdmin : voit tout
        if user.is_superuser or user.roles.filter(name="administrateur").exists():
            return base_qs.all()

        # 2. Admin de pharmacie ou Pharmacien : voit uniquement sa pharmacie
        pharmacie = get_pharmacie_user(user)
        if pharmacie:
            qs = base_qs.filter(pharmacie=pharmacie)
            # Filtrage par pharmacien optionnel
            pharmacien_id = self.request.query_params.get("pharmacien")
            if pharmacien_id:
                qs = qs.filter(created_by_id=pharmacien_id)
            return qs

        return base_qs.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        vente = serializer.save(created_by=self.request.user)
        from .sms_service import verifier_et_notifier_stock

        for ligne in vente.lignes.select_related("medicament").all():
            stock = (
                StockPharmacie.objects.filter(
                    pharmacie=vente.pharmacie,
                    medicament=ligne.medicament,
                )
                .select_related("pharmacie__proprietaire", "medicament")
                .first()
            )
            if stock:
                verifier_et_notifier_stock(stock)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        from django.db.models import Sum, Count

        qs = self.get_queryset()
        aujourd_hui = date.today()
        debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        debut_mois = aujourd_hui.replace(day=1)

        def agg(queryset):
            r = queryset.aggregate(nb_ventes=Count("id"), total_ca=Sum("total"))
            return {
                "nb_ventes": r["nb_ventes"] or 0,
                "total_ca": float(r["total_ca"] or 0),
            }

        return Response(
            {
                "aujourd_hui": agg(qs.filter(created_at__date=aujourd_hui)),
                "semaine"    : agg(qs.filter(created_at__date__gte=debut_semaine)),
                "mois"       : agg(qs.filter(created_at__date__gte=debut_mois)),
            }
        )

        
# ── Notifications ─────────────────────────────────────────────────────────────


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["pharmacie", "medicament", "type", "statut"]
    ordering_fields = ["created_at"]

    def _est_admin(self) -> bool:
        return IsAdminRole.est_admin(self.request.user)

    def get_queryset(self):
        base_qs = Notification.objects.select_related("pharmacie", "medicament")
        if self._est_admin():
            return base_qs.all()

        # ✅ CORRIGÉ
        pharmacie = get_pharmacie_user(self.request.user)
        if pharmacie:
            return base_qs.filter(pharmacie=pharmacie)
        return base_qs.none()

    @action(detail=False, methods=["get"], url_path="resume")
    def resume(self, request):
        from django.db.models import Count

        qs = self.get_queryset()
        return Response(
            {
                "par_type": list(qs.values("type").annotate(total=Count("id"))),
                "par_statut": list(qs.values("statut").annotate(total=Count("id"))),
                "total": qs.count(),
            }
        )


# ── ATC ───────────────────────────────────────────────────────────────────────


class ATCViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ATC.objects.prefetch_related("categories").all()
    serializer_class = ATCSerializer
    permission_classes = [IsAuthenticated]
