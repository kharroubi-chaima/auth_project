# accounts/serializers.py
from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings
import secrets
import string
from .models import User, Role, Permission, UserRole, RolePermission


# ── Must be defined before UserSerializer ──────────────────────────────────────
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


# ── User serializers ───────────────────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    """Serializer pour l'inscription publique (citoyen)"""
    password = serializers.CharField(
        write_only=True, required=True,
        style={'input_type': 'password'}
    )
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email','telephone',
            'password', 'status', 'date_joined',
            'is_active', 'is_staff', 'totp_enabled', 'roles'
        ]
        read_only_fields = ['id', 'date_joined', 'is_active', 'totp_enabled']

    def create(self, validated_data):
        password = validated_data.pop('password')
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


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer pour la modification du profil.
    Utilisé par le pharmacien et le citoyen pour mettre à jour leurs infos.
    Le mot de passe, is_active, is_staff, totp_enabled ne sont pas modifiables ici.
    """
    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'telephone',
            'status', 'date_joined', 'is_active',
            'is_staff', 'totp_enabled'
        ]
        read_only_fields = [
            'id', 'date_joined', 'is_active',
            'is_staff', 'totp_enabled', 'status'
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer pour changer le mot de passe (profil connecté)"""
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


class PharmacienCreateSerializer(serializers.ModelSerializer):
    """
    Serializer utilisé par l'admin pour créer un compte pharmacien.
    - Mot de passe généré automatiquement
    - Compte actif directement (sans TOTP)
    - Credentials envoyés par email
    - Le pharmacien peut compléter son profil via /users/me/update/
    """
    class Meta:
        model  = User
        fields = [
            'id', 'first_name', 'last_name', 'email',
            'status', 'date_joined', 'is_active',
            'is_staff', 'totp_enabled'
        ]
        read_only_fields = [
            'id', 'date_joined', 'is_active',
            'is_staff', 'totp_enabled'
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
        message = f"""
Bonjour {user.first_name} {user.last_name},

Votre compte pharmacien a été créé par l'administrateur.

Voici vos identifiants de connexion :
  - Email        : {user.email}
  - Mot de passe : {password_clair}

Connectez-vous sur : http://localhost:4200/signin

Après votre première connexion, vous pouvez :
  - Compléter votre profil
  - Changer votre mot de passe via Mon Profil → Changer le mot de passe

Cordialement,
L'équipe Gestion Pharmacie
        """.strip()
        send_mail(
            subject        = sujet,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            fail_silently  = False,
        )


# ── TOTP serializers ───────────────────────────────────────────────────────────
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