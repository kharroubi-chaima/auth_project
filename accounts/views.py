from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from .models import Role, Permission, UserRole, RolePermission
from .serializers import (
    UserSerializer, RoleSerializer, PermissionSerializer,
    UserRoleSerializer, RolePermissionSerializer, TOTPSetupSerializer, TOTPVerifySerializer, TOTPDisableSerializer
)
from .permissions import HasPermission, IsOwnerOrAdmin
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from rest_framework.views import APIView

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
    
    #partie ajouter pour la 2FA avec Google Authenticator
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def totp_setup(self, request):
        """Étape 1 : générer un secret et renvoyer l'URI pour le QR code."""
        user = request.user
        secret = user.generate_totp_secret()
        uri = user.get_totp_uri()
        serializer = TOTPSetupSerializer({'secret': secret, 'uri': uri})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def totp_verify(self, request):
        """Étape 2 : vérifier un premier code et activer la 2FA."""
        user = request.user
        serializer = TOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not user.totp_secret:
            return Response({'error': 'Aucun secret TOTP trouvé. Faites /totp_setup d\'abord.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Optionnel : vérifier le mot de passe pour confirmer l'identité
        password = serializer.validated_data.get('password')
        if password and not user.check_password(password):
            return Response({'error': 'Mot de passe incorrect.'},
                            status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data['code']

        if user.verify_totp(code):
            if not user.is_active:
                #bloc ajouté 
                user.is_active = True
                user.totp_enabled = True   # Active aussi la 2FA
                user.save(update_fields=['is_active', 'totp_enabled'])
                return Response({'status': 'Compte activé et TOTP activé.'})
                # fin du bloc ajouté

            user.totp_enabled = True
            user.save(update_fields=['totp_enabled'])
            return Response({'status': 'TOTP activé avec succès.'})
        else:
            return Response({'error': 'Code invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def totp_disable(self, request):
        """Désactiver la 2FA après vérification du mot de passe et éventuellement d'un code."""
        user = request.user
        serializer = TOTPDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Vérifier le mot de passe
        password = serializer.validated_data['password']
        if not user.check_password(password):
            return Response({'error': 'Mot de passe incorrect.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Si la 2FA est active, on peut exiger un code TOTP pour désactiver
        if user.totp_enabled:
            code = serializer.validated_data.get('code')
            if not code:
                return Response({'error': 'Code TOTP requis pour désactiver.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if not user.verify_totp(code):
                return Response({'error': 'Code TOTP invalide.'},
                                status=status.HTTP_400_BAD_REQUEST)

        # Désactivation
        user.totp_enabled = False
        user.totp_secret = None  # ou garder le secret mais désactiver
        user.save(update_fields=['totp_enabled', 'totp_secret'])
        return Response({'status': 'TOTP désactivé.'})


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

#Créer les endpoints pour la réinitialisation de mot de passe (sans token JWT, donc permission AllowAny)
class RequestPasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur non trouvé.'}, status=status.HTTP_404_NOT_FOUND)

        # Générer un token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Construire le lien (frontend) 
        reset_url = f"http://localhost:3000/reset-password/{uid}/{token}/"

        # Envoyer l'email
        send_mail(
            'Réinitialisation de mot de passe',
            f'Cliquez sur le lien suivant : {reset_url}',
            'noreply@example.com',
            [user.email],
            fail_silently=False,
        )
        return Response({'message': 'Email envoyé.'})
    


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Lien invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

        new_password = request.data.get('new_password')
        totp_code = request.data.get('totp_code')  # Optionnel si 2FA activée

        if user.totp_enabled:
            if not totp_code:
                return Response({'error': 'Code TOTP requis.'}, status=status.HTTP_400_BAD_REQUEST)
            if not user.verify_totp(totp_code):
                return Response({'error': 'Code TOTP invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        # Changer le mot de passe
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Mot de passe réinitialisé avec succès.'})# accounts/views.py

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Lien invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

        new_password = request.data.get('new_password')
        totp_code = request.data.get('totp_code')  # Optionnel si 2FA activée

        if user.totp_enabled:
            if not totp_code:
                return Response({'error': 'Code TOTP requis.'}, status=status.HTTP_400_BAD_REQUEST)
            if not user.verify_totp(totp_code):
                return Response({'error': 'Code TOTP invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        # Changer le mot de passe
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Mot de passe réinitialisé avec succès.'})
    
# la fin de la création des endpoints pour la réinitialisation de mot de passe

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