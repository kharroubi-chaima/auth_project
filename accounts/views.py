# accounts/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.shortcuts import redirect
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Role, Permission, UserRole, RolePermission
from .serializers import (
    UserSerializer, UserProfileSerializer,
    ChangePasswordSerializer, PharmacienCreateSerializer,
    RoleSerializer, PermissionSerializer,
    UserRoleSerializer, RolePermissionSerializer,
    TOTPSetupSerializer, TOTPVerifySerializer, TOTPDisableSerializer
)
from .permissions import HasPermission, IsOwnerOrAdmin

User = get_user_model()


# ─── JWT CUSTOM ───────────────────────────────────────────────────────────────

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'  # ✅ FIX : forcer le champ email

    def validate(self, attrs):
        email = attrs.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed('Email ou mot de passe incorrect.')

        if not user.check_password(attrs.get('password', '')):
            raise AuthenticationFailed('Email ou mot de passe incorrect.')

        if not user.is_active:
            raise AuthenticationFailed(
                'Compte non activé. Veuillez activer votre compte '
                'via Google Authenticator (TOTP).'
            )

        if user.status == 'suspended':
            raise AuthenticationFailed(
                'Compte suspendu. Contactez l\'administrateur.'
            )

        # ✅ FIX : s'assurer que attrs contient le bon champ pour super()
        attrs[self.username_field] = email
        data = super().validate(attrs)

        data['user'] = {
            'id'          : str(user.id),
            'email'       : user.email,
            'first_name'  : user.first_name,
            'last_name'   : user.last_name,
            'is_staff'    : user.is_staff,
            'totp_enabled': user.totp_enabled,
            'status'      : user.status,
            'roles'       : list(user.roles.values_list('name', flat=True)),
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]          # ✅ FIX : pas besoin d'auth pour login
    authentication_classes = []              # ✅ FIX : évite crash si pas de token

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            response.set_cookie(
                'access_token',
                response.data['access'],
                httponly=True,
                samesite='Lax',
                secure=False,
                path='/'
            )
            response.set_cookie(
                'refresh_token',
                response.data['refresh'],
                httponly=True,
                samesite='Lax',
                secure=False,
                path='/'
            )
        return response


# ─── USER VIEWSET ─────────────────────────────────────────────────────────────

class UserViewSet(viewsets.ModelViewSet):
    queryset         = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [AllowAny]
        elif self.action == 'create_pharmacien':
            self.permission_classes = [lambda: HasPermission('add_user')]
        elif self.action == 'list':
            self.permission_classes = [lambda: HasPermission('view_user')]
        elif self.action == 'retrieve':
            self.permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        elif self.action == 'destroy':
            self.permission_classes = [lambda: HasPermission('delete_user')]
        elif self.action in ['me', 'me_update', 'change_password']:
            self.permission_classes = [IsAuthenticated]
        elif self.action in ['assign_role', 'remove_role']:
            self.permission_classes = [lambda: HasPermission('change_user')]
        elif self.action == 'roles':
            self.permission_classes = [lambda: HasPermission('view_user')]
        elif self.action in ['totp_setup', 'totp_verify']:
            self.permission_classes = [AllowAny]
        elif self.action == 'totp_disable':
            self.permission_classes = [IsAuthenticated]
        else:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def me(self, request):
        user = request.user
        data = UserProfileSerializer(user).data
        data['roles'] = RoleSerializer(user.roles.all(), many=True).data
        return Response(data)

    @action(detail=False, methods=['put', 'patch'], url_path='me/update')
    def me_update(self, request):
        user       = request.user
        partial    = request.method == 'PATCH'
        serializer = UserProfileSerializer(
            user, data=request.data, partial=partial
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status' : 'Profil mis à jour avec succès.',
                'data'   : serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='me/change_password')
    def change_password(self, request):
        user       = request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(serializer.validated_data['ancien_password']):
            return Response(
                {'error': 'Ancien mot de passe incorrect.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['nouveau_password'])
        user.save()
        return Response({'status': 'Mot de passe modifié avec succès.'})

    @action(detail=False, methods=['post'])
    def create_pharmacien(self, request):
        serializer = PharmacienCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'status'  : 'Compte pharmacien créé avec succès.',
                    'email'   : user.email,
                    'message' : 'Les identifiants ont été envoyés par email au pharmacien.'
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        user    = self.get_object()
        role_id = request.data.get('role_id')
        try:
            role = Role.objects.get(id=role_id)
            _, created = UserRole.objects.get_or_create(user=user, role=role)
            if created:
                return Response({'status': 'role assigned'}, status=status.HTTP_201_CREATED)
            return Response({'status': 'already assigned'})
        except Role.DoesNotExist:
            return Response({'error': 'Role not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        user    = self.get_object()
        role_id = request.data.get('role_id')
        deleted, _ = UserRole.objects.filter(user=user, role_id=role_id).delete()
        if deleted:
            return Response({'status': 'role removed'})
        return Response({'error': 'role not assigned'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def roles(self, request, pk=None):
        user = self.get_object()
        return Response(RoleSerializer(user.roles.all(), many=True).data)

    @action(detail=False, methods=['post'])
    def totp_setup(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_active and user.totp_enabled:
            return Response({'error': 'Compte déjà activé.'}, status=status.HTTP_400_BAD_REQUEST)

        secret = user.generate_totp_secret()
        uri    = user.get_totp_uri()
        return Response(TOTPSetupSerializer({'secret': secret, 'uri': uri}).data)

    @action(detail=False, methods=['post'])
    def totp_verify(self, request):
        email = request.data.get('email')
        code  = request.data.get('code')

        if not email or not code:
            return Response({'error': 'Email et code requis.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        if not user.totp_secret:
            return Response({'error': 'Faites /totp_setup d\'abord.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.verify_totp(code):
            user.is_active    = True
            user.totp_enabled = True
            user.save(update_fields=['is_active', 'totp_enabled'])
            return Response({'status': 'Compte activé avec succès. Vous pouvez maintenant vous connecter.'})
        return Response({'error': 'Code invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def totp_disable(self, request):
        user       = request.user
        serializer = TOTPDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not user.check_password(serializer.validated_data['password']):
            return Response({'error': 'Mot de passe incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.totp_enabled:
            code = serializer.validated_data.get('code')
            if not code:
                return Response({'error': 'Code TOTP requis pour désactiver.'}, status=status.HTTP_400_BAD_REQUEST)
            if not user.verify_totp(code):
                return Response({'error': 'Code TOTP invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        user.totp_enabled = False
        user.totp_secret  = None
        user.save(update_fields=['totp_enabled', 'totp_secret'])
        return Response({'status': 'TOTP désactivé.'})


# ─── ROLES & PERMISSIONS ──────────────────────────────────────────────────────

class RoleViewSet(viewsets.ModelViewSet):
    queryset         = Role.objects.all()
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
        role    = self.get_object()
        perm_id = request.data.get('permission_id')
        try:
            permission = Permission.objects.get(id=perm_id)
            _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
            if created:
                return Response({'status': 'permission assigned'}, status=status.HTTP_201_CREATED)
            return Response({'status': 'already assigned'})
        except Permission.DoesNotExist:
            return Response({'error': 'Permission not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def remove_permission(self, request, pk=None):
        role    = self.get_object()
        perm_id = request.data.get('permission_id')
        deleted, _ = RolePermission.objects.filter(role=role, permission_id=perm_id).delete()
        if deleted:
            return Response({'status': 'permission removed'})
        return Response({'error': 'permission not assigned'}, status=status.HTTP_404_NOT_FOUND)


class PermissionViewSet(viewsets.ModelViewSet):
    queryset         = Permission.objects.all()
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


# ─── RESET PASSWORD SÉCURISÉ (cookies HttpOnly) ───────────────────────────────

class RequestPasswordResetView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'message': 'Si cet email existe, un lien a été envoyé.'})

        token     = default_token_generator.make_token(user)
        uid       = urlsafe_base64_encode(force_bytes(user.pk))
        reset_url = f"http://localhost:8000/auth/password-reset/validate/{uid}/{token}/"

        send_mail(
            'Réinitialisation de mot de passe – TuniService',
            f'Bonjour,\n\nCliquez sur ce lien pour réinitialiser votre mot de passe :\n{reset_url}\n\nCe lien expire dans 1 heure.\n\nSi vous n\'avez pas demandé cette réinitialisation, ignorez cet email.',
            'noreply@gestionpharmacie.tn',
            [user.email],
            fail_silently=False,
        )
        return Response({'message': 'Si cet email existe, un lien a été envoyé.'})


class PasswordResetValidateView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []

    def get(self, request, uidb64, token):
        try:
            uid  = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return redirect('http://localhost:4200/reset-password?error=invalid')

        if not default_token_generator.check_token(user, token):
            return redirect('http://localhost:4200/reset-password?error=expired')

        response = redirect('http://localhost:4200/reset-password?step=2')
        response.set_cookie('reset_uid',   uidb64, httponly=True, samesite='Lax', secure=False, max_age=3600, path='/')
        response.set_cookie('reset_token', token,  httponly=True, samesite='Lax', secure=False, max_age=3600, path='/')
        return response


class PasswordResetConfirmView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        uidb64 = request.COOKIES.get('reset_uid')
        token  = request.COOKIES.get('reset_token')

        if not uidb64 or not token:
            return Response(
                {'error': 'Session expirée. Veuillez refaire une demande de réinitialisation.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid  = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Lien invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

        new_password = request.data.get('new_password')
        if not new_password:
            return Response({'error': 'Nouveau mot de passe requis.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.totp_enabled:
            totp_code = request.data.get('totp_code')
            if not totp_code:
                return Response({'error': 'Code TOTP requis.'}, status=status.HTTP_400_BAD_REQUEST)
            if not user.verify_totp(totp_code):
                return Response({'error': 'Code TOTP invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        response = Response({'message': 'Mot de passe réinitialisé avec succès.'})
        response.delete_cookie('reset_uid',   path='/', samesite='Lax')
        response.delete_cookie('reset_token', path='/', samesite='Lax')
        return response


# ─── LOGOUT & TOKEN REFRESH ───────────────────────────────────────────────────

class LogoutView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')

        if refresh_token:
            try:
                token = JWTRefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        response = Response({'message': 'Déconnecté.'})
        response.delete_cookie('access_token',  path='/', samesite='Lax')
        response.delete_cookie('refresh_token', path='/', samesite='Lax')
        return response


class CookieTokenRefreshView(TokenRefreshView):
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({'detail': 'No refresh token'}, status=400)

        try:
            refresh     = RefreshToken(refresh_token)
            access      = str(refresh.access_token)
            new_refresh = str(refresh)
        except Exception:
            return Response({'detail': 'Invalid refresh token'}, status=400)

        response = Response({'detail': 'Token refreshed'})
        response.set_cookie('access_token',  access,      httponly=True, samesite='Lax', secure=False, path='/')
        response.set_cookie('refresh_token', new_refresh, httponly=True, samesite='Lax', secure=False, path='/')
        return response