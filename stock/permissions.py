from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """
    Permission personnalisée : l'utilisateur doit avoir le rôle 'admin'
    dans user_roles (UserRole model).

    Usage dans une vue :
        permission_classes = [IsAuthenticated, IsAdminRole]

    Ou via la méthode utilitaire statique dans un ViewSet :
        if IsAdminRole.est_admin(request.user):
            ...
    """

    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and
            request.user.is_authenticated and
            self.est_admin(request.user)
        )

    @staticmethod
    def est_admin(user) -> bool:
        """
        Vérifie si l'utilisateur possède le rôle 'admin'.
        Utilisable statiquement depuis n'importe quelle vue ou service.
        """
        return user.user_roles.filter(role__name='admin').exists()