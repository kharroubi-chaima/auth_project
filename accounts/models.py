from django.db import models

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


#   UserManager pour gérer la création des utilisateurs proprement (verif email, hash password, etc.)
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('L\'email est obligatoire')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    # Crée un admin Django
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

#   Modèle User personnalisé : qui va remplacé le user django par defaut 

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('suspended', 'Suspended')],
        default='active'
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    # on dit que la connexion se fait avec l'email et pas le username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email

#   Modèle Role

class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles_created'
    )
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('deactivate', 'Deactivate')],
        default='active'
    )

    def __str__(self):
        return self.name

#   Modèle Permission

class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permissions_created'
    )
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('deactivate', 'Deactivate')],
        default='active'
    )

    def __str__(self):
        return self.name

#   Table pivot User ↔ Role

class UserRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        #empéche la duplication d'un même rôle pour un même utilisateur
        unique_together = ('user', 'role')


#   Table pivot Role ↔ Permission

class RolePermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('role', 'permission')

#   Ajout des ManyToMany (facilite l'accès)

# Dans User (après définition de Role) :
User.add_to_class(
    'roles',
    models.ManyToManyField(Role, through='UserRole', related_name='users', blank=True)
)
# Dans Role (après définition de Permission) :
Role.add_to_class(
    'permissions',
    models.ManyToManyField(Permission, through='RolePermission', related_name='roles', blank=True)
)