# dashboard/permissions.py
from rest_framework.permissions import BasePermission
from pharmacies.models import Pharmacie


class EstPharmacien(BasePermission):
    """
    Autorise uniquement l'utilisateur authentifié qui est
    propriétaire d'au moins une pharmacie active.
    """
    message = "Accès réservé aux pharmaciens."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return Pharmacie.objects.filter(
            proprietaire=request.user,
            est_active=True
        ).exists()


class EstSuperAdmin(BasePermission):
    """
    Autorise uniquement les superadmins Django (is_staff=True ou is_superuser=True).
    Ces utilisateurs ont une vision globale sur TOUTES les pharmacies.
    """
    message = "Accès réservé aux super-administrateurs."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_staff or request.user.is_superuser


class EstPharmacienOuSuperAdmin(BasePermission):
    """
    Autorise les pharmaciens (propriétaire d'une pharmacie active)
    OU les superadmins.
    Pratique pour les endpoints mixtes.
    """
    message = "Accès réservé aux pharmaciens ou super-administrateurs."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        return Pharmacie.objects.filter(
            proprietaire=request.user,
            est_active=True
        ).exists()