from rest_framework.permissions import BasePermission


class HasPermission(BasePermission):
    """
    Vérifie si l'utilisateur possède une permission spécifique.
    Les superusers et les administrateurs (rôle) sont exemptés.
    """
    def __init__(self, perm_codename):
        self.perm_codename = perm_codename

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # Superuser a tous les droits
        if request.user.is_superuser:
            return True
        # Administrateur (rôle) a tous les droits
        if request.user.roles.filter(name='administrateur').exists():
            return True
        # Vérifie si l'utilisateur a cette permission via ses rôles
        return request.user.user_roles.filter(
            role__role_permissions__permission__name=self.perm_codename
        ).exists()


class IsOwnerOrAdmin(BasePermission):
    """
    Autorise l'accès si l'utilisateur est le propriétaire de l'objet ou est admin/superuser.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.roles.filter(name='administrateur').exists():
            return True
        return obj == request.user