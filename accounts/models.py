# accounts/models.py
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire")
        email = self.normalize_email(email)
        # is_active = True dès l'inscription (plus de blocage TOTP à l'inscription)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name   = models.CharField(max_length=150)
    last_name    = models.CharField(max_length=150)
    email        = models.EmailField(unique=True)
    telephone    = models.CharField(max_length=20, blank=True)
    status       = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('suspended', 'Suspended')],
        default='active'
    )
    is_staff     = models.BooleanField(default=False)
    is_active    = models.BooleanField(default=True)   # ← True par défaut maintenant
    date_joined  = models.DateTimeField(auto_now_add=True)
    totp_secret  = models.CharField(max_length=32, blank=True, null=True)
    totp_enabled = models.BooleanField(default=False)
    pharmacies_travail = models.ManyToManyField(
        'pharmacies.Pharmacie',
        blank=True,
        related_name='pharmaciens',
    )
    face_encoding = models.JSONField(null=True, blank=True)


    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    # ── TOTP helpers (utilisés uniquement pour le reset password) ──────────────

    def generate_totp_secret(self):
        import pyotp
        self.totp_secret = pyotp.random_base32()
        self.save(update_fields=['totp_secret'])
        return self.totp_secret

    def get_totp_uri(self):
        if not self.totp_secret:
            return None
        import pyotp
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name="GestionPharmacie"
        )

    def verify_totp(self, code):
        if not self.totp_secret:
            return False
        import pyotp
        return pyotp.TOTP(self.totp_secret).verify(code, valid_window=1)

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip() or self.email

    def get_short_name(self):
        return self.first_name or self.email

    # ── Helpers rôles ──────────────────────────────────────────────────────────

    def has_role(self, *role_names):
        return self.roles.filter(name__in=role_names).exists()

    @property
    def is_superadmin(self):
        return self.is_superuser or self.has_role('superadmin')

    @property
    def is_admin(self):
        return self.has_role('administrateur') or self.is_superadmin

    @property
    def is_pharmacien(self):
        return self.has_role('pharmacien')

    @property
    def is_citoyen(self):
        return self.has_role('citoyen')

    def __str__(self):
        return self.email


class Role(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='roles_created'
    )
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('deactivate', 'Deactivate')],
        default='active'
    )

    def __str__(self):
        return self.name


class Permission(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='permissions_created'
    )
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('deactivate', 'Deactivate')],
        default='active'
    )

    def __str__(self):
        return self.name


class UserRole(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role        = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'role')


class RolePermission(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role        = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission  = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('role', 'permission')


User.add_to_class(
    'roles',
    models.ManyToManyField(Role, through='UserRole', related_name='users', blank=True)
)
Role.add_to_class(
    'permissions',
    models.ManyToManyField(Permission, through='RolePermission', related_name='roles', blank=True)
)