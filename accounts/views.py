from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from .models import Role, Permission, UserRole, RolePermission
from .serializers import (
    UserSerializer, RoleSerializer, PermissionSerializer,
    UserRoleSerializer, RolePermissionSerializer
)
from .permissions import HasPermission, IsOwnerOrAdmin

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [AllowAny]
        elif self.action == 'list':
            self.permission_classes = [lambda: HasPermission('view_user')]
        elif self.action == 'retrieve':
            self.permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        elif self.action == 'destroy':
            self.permission_classes = [lambda: HasPermission('delete_user')]
        elif self.action == 'me':
            self.permission_classes = [IsAuthenticated]
        elif self.action in ['assign_role', 'remove_role']:
            self.permission_classes = [lambda: HasPermission('change_user')]
        elif self.action == 'roles':
            self.permission_classes = [lambda: HasPermission('view_user')]
        else:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Profil de l'utilisateur connecté (avec ses rôles)"""
        user = request.user
        serializer = self.get_serializer(user)
        data = serializer.data
        roles = RoleSerializer(user.roles.all(), many=True).data
        data['roles'] = roles
        return Response(data)

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        """Assigner un rôle à un utilisateur (permission change_user requise)"""
        user = self.get_object()
        role_id = request.data.get('role_id')
        try:
            role = Role.objects.get(id=role_id)
            user_role, created = UserRole.objects.get_or_create(user=user, role=role)
            if created:
                return Response({'status': 'role assigned'}, status=status.HTTP_201_CREATED)
            return Response({'status': 'already assigned'}, status=status.HTTP_200_OK)
        except Role.DoesNotExist:
            return Response({'error': 'Role not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        """Retirer un rôle à un utilisateur (permission change_user requise)"""
        user = self.get_object()
        role_id = request.data.get('role_id')
        deleted, _ = UserRole.objects.filter(user=user, role_id=role_id).delete()
        if deleted:
            return Response({'status': 'role removed'})
        return Response({'error': 'role not assigned'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def roles(self, request, pk=None):
        """Lister les rôles d'un utilisateur (permission view_user requise)"""
        user = self.get_object()
        serializer = RoleSerializer(user.roles.all(), many=True)
        return Response(serializer.data)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            self.permission_classes = [lambda: HasPermission('view_role')]
        elif self.action == 'create':
            self.permission_classes = [lambda: HasPermission('add_role')]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [lambda: HasPermission('change_role')]
        elif self.action == 'destroy':
            self.permission_classes = [lambda: HasPermission('delete_role')]
        elif self.action in ['assign_permission', 'remove_permission']:
            self.permission_classes = [lambda: HasPermission('change_role')]
        else:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def assign_permission(self, request, pk=None):
        """Assigner une permission à un rôle (permission change_role requise)"""
        role = self.get_object()
        perm_id = request.data.get('permission_id')
        try:
            permission = Permission.objects.get(id=perm_id)
            rp, created = RolePermission.objects.get_or_create(role=role, permission=permission)
            if created:
                return Response({'status': 'permission assigned'}, status=status.HTTP_201_CREATED)
            return Response({'status': 'already assigned'})
        except Permission.DoesNotExist:
            return Response({'error': 'Permission not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def remove_permission(self, request, pk=None):
        """Retirer une permission d'un rôle (permission change_role requise)"""
        role = self.get_object()
        perm_id = request.data.get('permission_id')
        deleted, _ = RolePermission.objects.filter(role=role, permission_id=perm_id).delete()
        if deleted:
            return Response({'status': 'permission removed'})
        return Response({'error': 'permission not assigned'}, status=status.HTTP_404_NOT_FOUND)


class PermissionViewSet(viewsets.ModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            self.permission_classes = [lambda: HasPermission('view_permission')]
        elif self.action == 'create':
            self.permission_classes = [lambda: HasPermission('add_permission')]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [lambda: HasPermission('change_permission')]
        elif self.action == 'destroy':
            self.permission_classes = [lambda: HasPermission('delete_permission')]
        else:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()