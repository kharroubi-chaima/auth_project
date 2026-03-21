from rest_framework.routers import DefaultRouter
from .views import (
    MedicamentViewSet,
    CategorieViewSet,
    StockPharmacieViewSet,
    MouvementStockViewSet,
    VenteViewSet,
)

router = DefaultRouter()

router.register(r'medicaments', MedicamentViewSet,     basename='medicament')
router.register(r'categories',  CategorieViewSet,      basename='categorie')
router.register(r'stocks',      StockPharmacieViewSet, basename='stock')
router.register(r'mouvements',  MouvementStockViewSet, basename='mouvement')
router.register(r'ventes',      VenteViewSet,          basename='vente')

urlpatterns = router.urls