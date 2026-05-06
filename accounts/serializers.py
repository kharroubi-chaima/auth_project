# accounts/serializers.py
from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings
import secrets
import string
from .models import User, Role, Permission, UserRole, RolePermission


# ── Rôles & permissions ────────────────────────────────────────────────────────

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Role
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Permission
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserRole
        fields = '__all__'


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RolePermission
        fields = '__all__'


# ── Inscription citoyen (sans TOTP) ───────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    """
    Inscription publique d'un citoyen.
    Le compte est actif immédiatement — pas de TOTP requis à l'inscription.
    Le TOTP reste disponible en option (setup + disable) mais n'est plus obligatoire.
    """
    password = serializers.CharField(
        write_only=True, required=True,
        style={'input_type': 'password'}
    )
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'telephone',
            'password', 'status', 'date_joined',
            'is_active', 'is_staff', 'totp_enabled', 'roles',
        ]
        read_only_fields = ['id', 'date_joined', 'is_active', 'totp_enabled']

    def create(self, validated_data):
        password = validated_data.pop('password')
        # is_active=True par défaut dans UserManager — connexion possible immédiatement
        user = User.objects.create_user(password=password, **validated_data)
        try:
            role_citoyen = Role.objects.get(name='citoyen')
            UserRole.objects.get_or_create(user=user, role=role_citoyen)
        except Role.DoesNotExist:
            pass
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


# ── Profil utilisateur connecté ───────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'telephone',
            'status', 'date_joined', 'is_active', 'is_staff', 'totp_enabled',
        ]
        read_only_fields = [
            'id', 'date_joined', 'is_active',
            'is_staff', 'totp_enabled', 'status',
        ]


# ── Changement de mot de passe ────────────────────────────────────────────────

class ChangePasswordSerializer(serializers.Serializer):
    ancien_password  = serializers.CharField(write_only=True)
    nouveau_password = serializers.CharField(write_only=True, min_length=8)

    def validate_nouveau_password(self, value):
        if not any(c.isupper() for c in value):
            raise serializers.ValidationError(
                "Le mot de passe doit contenir au moins une majuscule."
            )
        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError(
                "Le mot de passe doit contenir au moins un chiffre."
            )
        return value


# ── Création compte pharmacien (par admin/superadmin) ─────────────────────────

class PharmacienCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email',
            'status', 'date_joined', 'is_active', 'is_staff', 'totp_enabled',
        ]
        read_only_fields = [
            'id', 'date_joined', 'is_active', 'is_staff', 'totp_enabled',
        ]

    def _generer_mot_de_passe(self, longueur=12):
        alphabet = (
            string.ascii_uppercase +
            string.ascii_lowercase +
            string.digits +
            "!@#$%^&*"
        )
        mdp = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*"),
        ]
        mdp += [secrets.choice(alphabet) for _ in range(longueur - 4)]
        secrets.SystemRandom().shuffle(mdp)
        return ''.join(mdp)

    def create(self, validated_data):
        password_clair = self._generer_mot_de_passe()
        user = User.objects.create_user(password=password_clair, **validated_data)
        user.is_active = True
        user.save(update_fields=['is_active'])
        try:
            role_pharmacien = Role.objects.get(name='pharmacien')
            UserRole.objects.get_or_create(user=user, role=role_pharmacien)
        except Role.DoesNotExist:
            pass
        self._envoyer_email_credentials(user, password_clair)
        return user

    def _envoyer_email_credentials(self, user, password_clair):
        sujet   = "Vos identifiants de connexion — Gestion Pharmacie"
        message = (
            f"Bonjour {user.first_name} {user.last_name},\n\n"
            f"Votre compte pharmacien a été créé.\n\n"
            f"Email        : {user.email}\n"
            f"Mot de passe : {password_clair}\n\n"
            f"Connectez-vous sur : http://localhost:4200/connexion\n\n"
            f"Cordialement,\nL'équipe Gestion Pharmacie"
        )
        send_mail(
            subject        = sujet,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            fail_silently  = False,
        )


# ── Création compte administrateur (par superadmin uniquement) ────────────────

class AdminCreateSerializer(serializers.ModelSerializer):
    """
    Crée un compte administrateur (rôle 'administrateur').
    Réservé au superadmin.
    """
    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'telephone',
            'status', 'date_joined', 'is_active', 'is_staff', 'totp_enabled',
        ]
        read_only_fields = [
            'id', 'date_joined', 'is_active', 'is_staff', 'totp_enabled',
        ]

    def _generer_mot_de_passe(self, longueur=14):
        alphabet = (
            string.ascii_uppercase +
            string.ascii_lowercase +
            string.digits +
            "!@#$%^&*"
        )
        mdp = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*"),
        ]
        mdp += [secrets.choice(alphabet) for _ in range(longueur - 4)]
        secrets.SystemRandom().shuffle(mdp)
        return ''.join(mdp)

    def create(self, validated_data):
        password_clair = self._generer_mot_de_passe()
        user = User.objects.create_user(password=password_clair, **validated_data)
        user.is_active = True
        user.is_staff  = True
        user.save(update_fields=['is_active', 'is_staff'])
        try:
            role_admin = Role.objects.get(name='administrateur')
            UserRole.objects.get_or_create(user=user, role=role_admin)
        except Role.DoesNotExist:
            pass
        self._envoyer_email_credentials(user, password_clair)
        return user

    def _envoyer_email_credentials(self, user, password_clair):
        sujet   = "Compte administrateur créé — Gestion Pharmacie"
        message = (
            f"Bonjour {user.first_name} {user.last_name},\n\n"
            f"Un compte administrateur a été créé pour vous.\n\n"
            f"Email        : {user.email}\n"
            f"Mot de passe : {password_clair}\n\n"
            f"Connectez-vous sur : http://localhost:4200/signin\n\n"
            f"Cordialement,\nL'équipe Gestion Pharmacie"
        )
        send_mail(
            subject        = sujet,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            fail_silently  = False,
        )


# ── Gestion des comptes par superadmin ────────────────────────────────────────

class UserAdminEditSerializer(serializers.ModelSerializer):
    """
    Permet au superadmin de modifier n'importe quel champ utilisateur,
    y compris le statut (suspended/active).
    """
    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'telephone',
            'status', 'is_active', 'is_staff', 'totp_enabled', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined', 'totp_enabled']


# ── TOTP serializers (reset password) ────────────────────────────────────────

class TOTPSetupSerializer(serializers.Serializer):
    secret = serializers.CharField(read_only=True)
    uri    = serializers.CharField(read_only=True)


class TOTPVerifySerializer(serializers.Serializer):
    code     = serializers.CharField(max_length=6, min_length=6)
    password = serializers.CharField(write_only=True, required=False)

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError(
                "Le code doit contenir uniquement des chiffres."
            )
        return value


class TOTPDisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    code     = serializers.CharField(max_length=6, min_length=6, required=False)