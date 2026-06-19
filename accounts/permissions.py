# accounts/permissions.py
from rest_framework.permissions import BasePermission


class HasPermission(BasePermission):
    """
    Vérifie si l'utilisateur possède une permission spécifique via ses rôles.
    Administrateur et gérant sont toujours exemptés.
    """
    def __init__(self, perm_codename):
        self.perm_codename = perm_codename

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if request.user.roles.filter(name__in=['administrateur', 'gérant']).exists():
            return True
        return request.user.user_roles.filter(
            role__role_permissions__permission__name=self.perm_codename
        ).exists()


class IsOwnerOrAdmin(BasePermission):
    """
    Autorise l'accès si l'utilisateur est le propriétaire ou un admin/superadmin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if request.user.roles.filter(name__in=['administrateur', 'gérant']).exists():
            return True
        return obj == request.user


class IsSuperAdmin(BasePermission):
    """
    Réservé exclusivement à l'administrateur (superuser Django ou rôle 'administrateur').
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.roles.filter(name='administrateur').exists()


class IsAdminOrSuperAdmin(BasePermission):
    """
    Autorise les gérants et administrateurs.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.roles.filter(name__in=['administrateur', 'gérant']).exists()