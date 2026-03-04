# localisations/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GouvernoratViewSet, DelegationViewSet

router = DefaultRouter()
router.register(r'gouvernorats', GouvernoratViewSet, basename='gouvernorat')
router.register(r'delegations', DelegationViewSet, basename='delegation')

urlpatterns = [
    path('', include(router.urls)),
]