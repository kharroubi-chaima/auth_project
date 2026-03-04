import django_filters
from .models import Pharmacie

class PharmacieFilter(django_filters.FilterSet):
    categorie = django_filters.CharFilter(field_name='categorie', lookup_expr='exact')
    
    class Meta:
        model = Pharmacie
        fields = ['delegation', 'delegation__gouvernorat', 'est_active', 'categorie']