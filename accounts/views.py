# accounts/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken, RefreshToken as JWTRefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.shortcuts import redirect

from .models import Role, Permission, UserRole, RolePermission
from .serializers import (
    UserSerializer, UserProfileSerializer,
    ChangePasswordSerializer, PharmacienCreateSerializer,
    AdminCreateSerializer, UserAdminEditSerializer,
    RoleSerializer, PermissionSerializer,
    UserRoleSerializer, RolePermissionSerializer,
    TOTPSetupSerializer, TOTPVerifySerializer, TOTPDisableSerializer,
)
from .permissions import HasPermission, IsOwnerOrAdmin, IsSuperAdmin, IsAdminOrSuperAdmin

User = get_user_model()


# ── JWT custom ────────────────────────────────────────────────────────────────

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed('Email ou mot de passe incorrect.')

        if not user.check_password(attrs.get('password', '')):
            raise AuthenticationFailed('Email ou mot de passe incorrect.')

        if not user.is_active:
            raise AuthenticationFailed('Compte désactivé. Contactez l\'administrateur.')

        if user.status == 'suspended':
            raise AuthenticationFailed('Compte suspendu. Contactez l\'administrateur.')

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
    serializer_class   = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            response.set_cookie('access_token',  response.data['access'],
                                httponly=True, samesite='Lax', secure=False, path='/')
            response.set_cookie('refresh_token', response.data['refresh'],
                                httponly=True, samesite='Lax', secure=False, path='/')
        return response


# ── UserViewSet (citoyens, profil) ────────────────────────────────────────────

class UserViewSet(viewsets.ModelViewSet):
    queryset         = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            # Inscription publique citoyen — sans TOTP
            self.permission_classes = [AllowAny]
        elif self.action == 'create_pharmacien':
            # Admin ou superadmin peut créer un pharmacien
            self.permission_classes = [IsAdminOrSuperAdmin]
        elif self.action == 'list':
            self.permission_classes = [IsAdminOrSuperAdmin]
        elif self.action == 'retrieve':
            self.permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        elif self.action == 'destroy':
            self.permission_classes = [IsSuperAdmin]
        elif self.action in ['me', 'me_update', 'change_password']:
            self.permission_classes = [IsAuthenticated]
        elif self.action in ['assign_role', 'remove_role']:
            self.permission_classes = [IsSuperAdmin]
        elif self.action == 'roles':
            self.permission_classes = [IsAdminOrSuperAdmin]
        elif self.action in ['totp_setup', 'totp_verify', 'totp_disable']:
            # TOTP disponible mais non obligatoire
            self.permission_classes = [IsAuthenticated]
        elif self.action == 'suspend':
            self.permission_classes = [IsAdminOrSuperAdmin]
        elif self.action == 'activate':
            self.permission_classes = [IsAdminOrSuperAdmin]
        else:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    # ── Profil personnel ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def me(self, request):
        user = request.user
        return Response ({
            'id' : str(user.id),
            'email' : user.email,
            'last_name' : user.last_name,
            'first_name' : user.first_name,
            'is_staff' : user.is_staff,
            'totp_enabled' : user.totp_enabled,
            'status' : user.status,
            'roles' : list(user.roles.values_list('name', flat=True)),
        })

    @action(detail=False, methods=['put', 'patch'], url_path='me/update')
    def me_update(self, request):
        partial    = request.method == 'PATCH'
        serializer = UserProfileSerializer(request.user, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'Profil mis à jour.', 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response( serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        
        if not user.check_password(serializer.validated_data['ancien_password']):
            return Response(
                {'error': 'Ancien mot de passe incorrect.'}, 
                status=status.HTTP_400_BAD_REQUEST
                )
        user.set_password(serializer.validated_data['nouveau_password'])
        user.save()
        return Response({'status': 'Mot de passe changé avec succès.'})
    # ── Création pharmacien (admin/superadmin) ────────────────────────────────

    @action(detail=False, methods=['post'])
    def create_pharmacien(self, request):
        serializer = PharmacienCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'status': 'Compte pharmacien créé.', 'email': user.email},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── Gestion des rôles ─────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        user    = self.get_object()
        role_id = request.data.get('role_id')
        try:
            role = Role.objects.get(id=role_id)
            _, created = UserRole.objects.get_or_create(user=user, role=role)
            if created:
                return Response({'status': 'Rôle assigné.'}, status=status.HTTP_201_CREATED)
            return Response({'status': 'Rôle déjà assigné.'})
        except Role.DoesNotExist:
            return Response({'error': 'Rôle introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        user    = self.get_object()
        role_id = request.data.get('role_id')
        deleted, _ = UserRole.objects.filter(user=user, role_id=role_id).delete()
        if deleted:
            return Response({'status': 'Rôle retiré.'})
        return Response({'error': 'Rôle non assigné.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def roles(self, request, pk=None):
        user = self.get_object()
        return Response(RoleSerializer(user.roles.all(), many=True).data)

    # ── Suspension / activation (admin/superadmin) ────────────────────────────

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        user = self.get_object()
        user.status = 'suspended'
        user.save(update_fields=['status'])
        return Response({'status': f'Compte {user.email} suspendu.'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.status    = 'active'
        user.is_active = True
        user.save(update_fields=['status', 'is_active'])
        return Response({'status': f'Compte {user.email} activé.'})

    # ── TOTP (optionnel — setup / disable) ───────────────────────────────────
    # Le TOTP n'est plus requis à l'inscription.
    # Il est utilisé uniquement lors du reset password si activé.

    @action(detail=False, methods=['post'])
    def totp_setup(self, request):
        user   = request.user
        secret = user.generate_totp_secret()
        uri    = user.get_totp_uri()
        return Response(TOTPSetupSerializer({'secret': secret, 'uri': uri}).data)

    @action(detail=False, methods=['post'])
    def totp_verify(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'Code requis.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        if not user.totp_secret:
            return Response({'error': 'Faites /totp_setup d\'abord.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.verify_totp(code):
            user.totp_enabled = True
            user.save(update_fields=['totp_enabled'])
            return Response({'status': 'TOTP activé avec succès.'})
        return Response({'error': 'Code invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def totp_disable(self, request):
        serializer = TOTPDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
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


# ── SuperAdmin — gestion des administrateurs ──────────────────────────────────

class SuperAdminUserViewSet(viewsets.ModelViewSet):
    """
    Endpoint exclusif superadmin :
    - Créer / lister / modifier / supprimer des administrateurs
    - Modifier n'importe quel compte (citoyen, pharmacien, admin)
    - Suspendre / réactiver des comptes
    - Voir les propriétaires de pharmacie et leurs pharmacies
    """
    serializer_class   = UserAdminEditSerializer
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        role_filter = self.request.query_params.get('role')
        status_filter = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        qs = User.objects.all().prefetch_related('roles', 'pharmacies')
        if role_filter:
            qs = qs.filter(roles__name=role_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))
        return qs

    def get_serializer_class(self):
        if self.action == 'create_admin':
            return AdminCreateSerializer
        if self.action == 'create_pharmacien':
            return PharmacienCreateSerializer
        return UserAdminEditSerializer

    # ── Création admin ─────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='create-admin')
    def create_admin(self, request):
        serializer = AdminCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'status': 'Compte administrateur créé.', 'email': user.email},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── Création propriétaire pharmacie ───────────────────────

    @action(detail=False, methods=['post'], url_path='create-pharmacien')
    def create_pharmacien(self, request):
        serializer = PharmacienCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'status': 'Compte pharmacien créé.', 'email': user.email},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── Suspension ────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        user = self.get_object()
        user.status = 'suspended'
        user.save(update_fields=['status'])
        return Response({'status': f'Compte {user.email} suspendu.'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.status    = 'active'
        user.is_active = True
        user.save(update_fields=['status', 'is_active'])
        return Response({'status': f'Compte {user.email} activé.'})

    # ── Voir les pharmacies d'un propriétaire ─────────────────

    @action(detail=True, methods=['get'])
    def pharmacies(self, request, pk=None):
        user = self.get_object()
        from pharmacies.serializers import PharmacieListSerializer
        qs   = user.pharmacies.all()
        return Response(PharmacieListSerializer(qs, many=True).data)

    # ── Modifier un champ citoyen ─────────────────────────────

    @action(detail=True, methods=['patch'], url_path='edit')
    def edit_user(self, request, pk=None):
        user       = self.get_object()
        serializer = UserAdminEditSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'Compte mis à jour.', 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Rôles & Permissions ───────────────────────────────────────────────────────

class RoleViewSet(viewsets.ModelViewSet):
    queryset         = Role.objects.all()
    serializer_class = RoleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            self.permission_classes = [IsAdminOrSuperAdmin]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsSuperAdmin]
        elif self.action in ['assign_permission', 'remove_permission']:
            self.permission_classes = [IsSuperAdmin]
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
                return Response({'status': 'Permission assignée.'}, status=status.HTTP_201_CREATED)
            return Response({'status': 'Déjà assignée.'})
        except Permission.DoesNotExist:
            return Response({'error': 'Permission introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def remove_permission(self, request, pk=None):
        role    = self.get_object()
        perm_id = request.data.get('permission_id')
        deleted, _ = RolePermission.objects.filter(role=role, permission_id=perm_id).delete()
        if deleted:
            return Response({'status': 'Permission retirée.'})
        return Response({'error': 'Permission non assignée.'}, status=status.HTTP_404_NOT_FOUND)


class PermissionViewSet(viewsets.ModelViewSet):
    queryset         = Permission.objects.all()
    serializer_class = PermissionSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            self.permission_classes = [IsAdminOrSuperAdmin]
        else:
            self.permission_classes = [IsSuperAdmin]
        return super().get_permissions()


# ── Reset password (avec TOTP si activé) ─────────────────────────────────────

class RequestPasswordResetView(APIView):
    """
    Envoie un email avec un lien de réinitialisation.
    Si le compte a TOTP activé, un code sera demandé lors de la confirmation.
    """
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
        reset_url = f"http://localhost:8000/api/auth/password-reset/validate/{uid}/{token}/"

        send_mail(
            'Réinitialisation de mot de passe – Gestion Pharmacie',
            (
                f'Bonjour,\n\n'
                f'Cliquez sur ce lien pour réinitialiser votre mot de passe :\n{reset_url}\n\n'
                f'Ce lien expire dans 1 heure.\n\n'
                f'Si vous n\'avez pas demandé cette réinitialisation, ignorez cet email.'
            ),
            'noreply@gestionpharmacie.tn',
            [user.email],
            fail_silently=False,
        )
        return Response({'message': 'Si cet email existe, un lien a été envoyé.'})


class PasswordResetValidateView(APIView):
    """
    Étape 2 : L'utilisateur clique sur le lien reçu par email.
    Valide le token et redirige vers le formulaire de nouveau mot de passe.
    """
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

        return redirect(
            f'http://localhost:4200/reset-password?step=2&uid={uidb64}&token={token}'
        )


class PasswordResetConfirmView(APIView):
    """
    Étape 3 : L'utilisateur saisit son nouveau mot de passe.
    - Change le mot de passe
    - Génère un secret TOTP (si l'utilisateur n'en a pas)
    - Retourne le QR Code en base64 + un nouveau token pour l'étape TOTP
    """
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        uidb64 = request.data.get('uid')
        token  = request.data.get('token')

        if not uidb64 or not token:
            return Response(
                {'error': 'Session expirée. Veuillez refaire une demande.'},
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

        # ── Changer le mot de passe ───────────────────────────────
        user.set_password(new_password)
        user.save()

        # ── Générer un secret TOTP si l'utilisateur n'en a pas ────
        if not user.totp_secret:
            user.generate_totp_secret()

        # ── Nouveau token (l'ancien est invalidé par le changement de mdp) ──
        new_token = default_token_generator.make_token(user)

        # ── Générer le QR Code en base64 ──────────────────────────
        import qrcode, base64
        from io import BytesIO
        uri = user.get_totp_uri()
        buf = BytesIO()
        qrcode.make(uri).save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        return Response({
            'message': 'Mot de passe changé. Veuillez scanner le QR Code.',
            'qr': f'data:image/png;base64,{qr_b64}',
            'uid': uidb64,
            'token': new_token,
        })


class PasswordResetTotpVerifyView(APIView):
    """
    Étape 4 : Vérification du code TOTP après reset password.
    L'utilisateur a scanné le QR Code avec Google Authenticator
    et saisit les 6 chiffres.
    Si le code est valide → TOTP activé → succès → redirection vers connexion.
    """
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        uidb64    = request.data.get('uid')
        token     = request.data.get('token')
        totp_code = request.data.get('totp_code')

        if not uidb64 or not token:
            return Response(
                {'error': 'Session expirée. Veuillez refaire une demande.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not totp_code:
            return Response(
                {'error': 'Code TOTP requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid  = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Lien invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.verify_totp(totp_code):
            return Response({'error': 'Code TOTP invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Activer le TOTP et confirmer le reset ─────────────────
        user.totp_enabled = True
        user.save(update_fields=['totp_enabled'])

        return Response({'message': 'Mot de passe réinitialisé avec succès. Vous pouvez vous connecter.'})


# ── Logout & refresh ──────────────────────────────────────────────────────────

class LogoutView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')
        if refresh_token:
            try:
                JWTRefreshToken(refresh_token).blacklist()
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