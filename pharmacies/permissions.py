# pharmacies/permissions.py
from rest_framework.permissions import BasePermission


class HasPermission(BasePermission):
    perm_name = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.roles.filter(
            role_permissions__permission__name=self.perm_name,
            role_permissions__permission__status='active'
        ).exists()


def require_perm(perm_name):
    return type(
        f'Has_{perm_name}',
        (HasPermission,),
        {'perm_name': perm_name}
    )