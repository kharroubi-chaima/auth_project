from rest_framework.routers import DefaultRouter
from .views import (
    ATCViewSet,
    MedicamentViewSet,
    CategorieViewSet,
    NotificationViewSet,
    StockPharmacieViewSet,
    MouvementStockViewSet,
    VenteViewSet,
)

router = DefaultRouter()

router.register(r'medicaments', MedicamentViewSet,     basename='medicament')
router.register(r'categories',  CategorieViewSet,      basename='categorie')
router.register(r'atc', ATCViewSet, basename='atc')
router.register(r'stocks',      StockPharmacieViewSet, basename='stock')
router.register(r'mouvements',  MouvementStockViewSet, basename='mouvement')
router.register(r'ventes',      VenteViewSet,          basename='vente')
router.register(r'notifications', NotificationViewSet,    basename='notification')  # ← ajouter


urlpatterns = router.urls