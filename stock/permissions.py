from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and
            request.user.is_authenticated and
            self.est_admin(request.user)
        )

    @staticmethod
    def est_admin(user) -> bool:
        return (
            user.is_staff or
            user.is_superuser or
            user.roles.filter(name__in=['administrateur', 'superadmin']).exists()
        )