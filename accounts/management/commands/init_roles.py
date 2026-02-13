from django.core.management.base import BaseCommand
from accounts.models import Role, Permission, RolePermission


class Command(BaseCommand):
    help = 'Initialise les rôles et permissions par défaut avec leurs assignations'

    def handle(self, *args, **options):
        # 1. Création des rôles
        role_admin, _ = Role.objects.get_or_create(name='administrateur')
        role_pharma, _ = Role.objects.get_or_create(name='pharmacien')
        role_citoyen, _ = Role.objects.get_or_create(name='citoyen')

        # 2. Création des permissions
        permissions = [
            'view_user', 'add_user', 'change_user', 'delete_user',
            'view_role', 'add_role', 'change_role', 'delete_role',
            'view_permission', 'add_permission', 'change_permission', 'delete_permission',
        ]
        perm_objects = {}
        for perm_name in permissions:
            perm, _ = Permission.objects.get_or_create(name=perm_name)
            perm_objects[perm_name] = perm

        # 3. Assignation des permissions aux rôles
        # Administrateur : toutes les permissions
        for perm in perm_objects.values():
            RolePermission.objects.get_or_create(role=role_admin, permission=perm)

        # Pharmacien : permissions en lecture seule
        readonly_perms = ['view_user', 'view_role', 'view_permission']
        for perm_name in readonly_perms:
            RolePermission.objects.get_or_create(
                role=role_pharma,
                permission=perm_objects[perm_name]
            )

        # Citoyen : aucune permission explicite

        self.stdout.write(self.style.SUCCESS(
            '✅ Rôles, permissions et assignations créés avec succès.'
        ))