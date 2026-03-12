# pharmacies/filters.py
import django_filters
from .models import Pharmacie
from localisations.models import Gouvernorat


class PharmacieFilter(django_filters.FilterSet):
    # ✅ UUID car gouvernorat.id est un UUID
    gouvernorat = django_filters.UUIDFilter(
        field_name='delegation__gouvernorat__id',
        lookup_expr='exact',
        label='Gouvernorat'
    )

    # ✅ "categorie" → filtre direct
    categorie = django_filters.CharFilter(
        field_name='categorie',
        lookup_expr='exact',
        label='Catégorie'
    )

    # ✅ "est_active" → filtre booléen
    est_active = django_filters.BooleanFilter(
        field_name='est_active',
        label='Est active'
    )

    class Meta:
        model  = Pharmacie
        fields = ['gouvernorat', 'categorie', 'est_active']