# localisations/views.py
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Gouvernorat, Delegation
from .serializers import GouvernoratSerializer, DelegationSerializer


class GouvernoratViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Gouvernorat.objects.all()
    serializer_class = GouvernoratSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom']


class DelegationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Delegation.objects.select_related('gouvernorat').all()
    serializer_class = DelegationSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['gouvernorat']
    search_fields = ['nom']