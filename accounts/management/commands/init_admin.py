# accounts/management/commands/init_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role, Permission, UserRole, RolePermission

User = get_user_model()


class Command(BaseCommand):
    help = 'Initialise les permissions, rôles, et crée les comptes superadmin et administrateur'

    # ─── COORDONNÉES SUPERADMIN ───────────────────────────────
    SUPERADMIN_EMAIL      = 'superadmin@gestionpharmacie.tn'
    SUPERADMIN_PASSWORD   = 'SuperAdmin@2026!'
    SUPERADMIN_FIRST_NAME = 'Super'
    SUPERADMIN_LAST_NAME  = 'Admin'

    # ─── COORDONNÉES ADMIN ────────────────────────────────────
    ADMIN_EMAIL      = 'admin@gestionpharmacie.tn'
    ADMIN_PASSWORD   = 'Admin@2026!'
    ADMIN_FIRST_NAME = 'Admin'
    ADMIN_LAST_NAME  = 'Principal'

    # ─── DÉFINITION DES PERMISSIONS PAR CATÉGORIE ─────────────
    PERMISSIONS = {
        'utilisateurs': [
            'view_user',
            'add_user',
            'change_user',
            'delete_user',
        ],
        'roles': [
            'view_role',
            'add_role',
            'change_role',
            'delete_role',
        ],
        'permissions': [
            'view_permission',
            'add_permission',
            'change_permission',
            'delete_permission',
        ],
        'pharmacies': [
            'view_pharmacie',
            'add_pharmacie',
            'change_pharmacie',
            'delete_pharmacie',
        ],
        'horaires': [
            'view_horaire',
            'add_horaire',
            'change_horaire',
            'delete_horaire',
        ],
        'gardes': [
            'view_garde',
            'add_garde',
            'change_garde',
            'delete_garde',
        ],
        'jours_feries': [
            'view_jourferie',
            'add_jourferie',
            'change_jourferie',
            'delete_jourferie',
        ],
        'localisations': [
            'view_gouvernorat',
            'add_gouvernorat',
            'change_gouvernorat',
            'delete_gouvernorat',
            'view_delegation',
            'add_delegation',
            'change_delegation',
            'delete_delegation',
        ],
        'public': [
            'view_pharmacie_publique',
            'view_garde_publique',
            'view_horaire_publique',
        ],
        # Permissions spécifiques superadmin
        'superadmin': [
            'manage_admins',        # créer / supprimer des administrateurs
            'manage_all_users',     # accès total à tous les comptes
            'manage_all_pharmacies', # accès total à toutes les pharmacies
            'suspend_account',      # suspendre n'importe quel compte
        ],
    }

    # ─── PERMISSIONS PAR RÔLE ─────────────────────────────────
    ROLE_PERMISSIONS = {

        # ── Superadmin : accès absolu ─────────────────────────
        # Peut tout faire + gestion des administrateurs
        'superadmin': '__all__',

        # ── Administrateur : accès large (sauf gestion des admins) ─
        # Ne peut PAS créer d'autres administrateurs
        # Ne peut PAS supprimer des pharmacies
        'administrateur': [
            'view_user',
            'add_user',         # créer des pharmaciens
            'change_user',
            'delete_user',
            'view_role',
            'view_permission',
            'view_pharmacie',
            'add_pharmacie',
            'change_pharmacie',
            'view_horaire',
            'add_horaire',
            'change_horaire',
            'delete_horaire',
            'view_garde',
            'add_garde',
            'change_garde',
            'delete_garde',
            'view_jourferie',
            'add_jourferie',
            'change_jourferie',
            'delete_jourferie',
            'view_gouvernorat',
            'view_delegation',
            'view_pharmacie_publique',
            'view_garde_publique',
            'view_horaire_publique',
            'suspend_account',
        ],

        # ── Pharmacien : gère sa pharmacie ────────────────────
        'pharmacien': [
            'view_user',
            'view_role',
            'view_permission',
            'view_pharmacie',
            'change_pharmacie',
            'view_horaire',
            'add_horaire',
            'change_horaire',
            'delete_horaire',
            'view_garde',
            'add_garde',
            'change_garde',
            'view_jourferie',
            'view_gouvernorat',
            'view_delegation',
            'view_pharmacie_publique',
            'view_garde_publique',
            'view_horaire_publique',
        ],

        # ── Citoyen : consultation publique uniquement ────────
        'citoyen': [
            'view_pharmacie_publique',
            'view_garde_publique',
            'view_horaire_publique',
        ],
    }

    def handle(self, *args, **options):

        # ── ÉTAPE 1 : Permissions ──────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('\n🔐 Étape 1 : Création des permissions...'))
        perm_objects   = {}
        total_created  = 0
        total_existing = 0

        for categorie, perms in self.PERMISSIONS.items():
            self.stdout.write(f'\n   📂 {categorie} :')
            for perm_name in perms:
                perm, created = Permission.objects.get_or_create(name=perm_name)
                perm_objects[perm_name] = perm
                if created:
                    total_created += 1
                    self.stdout.write(f'      ✅ {perm_name}')
                else:
                    total_existing += 1
                    self.stdout.write(f'      ⏭️  {perm_name} (existant)')

        self.stdout.write(self.style.SUCCESS(
            f'\n   → {total_created} créées, {total_existing} déjà existantes'
        ))

        # ── ÉTAPE 2 : Rôles ───────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('\n👥 Étape 2 : Création des rôles...'))
        roles = {}
        for role_name in self.ROLE_PERMISSIONS.keys():
            role, created = Role.objects.get_or_create(name=role_name)
            roles[role_name] = role
            flag = '✅ Créé' if created else '⏭️  Existant'
            self.stdout.write(f'   {flag} → {role_name}')

        # ── ÉTAPE 3 : Assignation permissions → rôles ─────────
        self.stdout.write(self.style.HTTP_INFO(
            '\n🔗 Étape 3 : Assignation des permissions aux rôles...'
        ))
        all_perms = [
            perm_name
            for perms in self.PERMISSIONS.values()
            for perm_name in perms
        ]

        for role_name, perms in self.ROLE_PERMISSIONS.items():
            role            = roles[role_name]
            perms_to_assign = all_perms if perms == '__all__' else perms
            assigned        = 0
            already         = 0

            for perm_name in perms_to_assign:
                perm = perm_objects.get(perm_name)
                if not perm:
                    self.stdout.write(self.style.WARNING(
                        f'      ⚠️  Permission introuvable : {perm_name}'
                    ))
                    continue
                _, created = RolePermission.objects.get_or_create(role=role, permission=perm)
                if created:
                    assigned += 1
                else:
                    already += 1

            self.stdout.write(
                f'   ✅ {role_name:<20} → '
                f'{assigned} assignées, {already} déjà existantes '
                f'({len(perms_to_assign)} au total)'
            )

        # ── ÉTAPE 4 : Compte superadmin ───────────────────────
        self.stdout.write(self.style.HTTP_INFO(
            '\n👑 Étape 4 : Création du compte superadmin...'
        ))
        superadmin, created = User.objects.get_or_create(
            email=self.SUPERADMIN_EMAIL,
            defaults={
                'first_name'  : self.SUPERADMIN_FIRST_NAME,
                'last_name'   : self.SUPERADMIN_LAST_NAME,
                'is_staff'    : True,
                'is_superuser': True,
                'is_active'   : True,
                'status'      : 'active',
            }
        )
        if created:
            superadmin.set_password(self.SUPERADMIN_PASSWORD)
            superadmin.save()
            self.stdout.write(self.style.SUCCESS(
                f'\n   ✅ Superadmin créé !\n'
                f'      Email    : {self.SUPERADMIN_EMAIL}\n'
                f'      Password : {self.SUPERADMIN_PASSWORD}\n'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\n   ⏭️  Superadmin déjà existant ({self.SUPERADMIN_EMAIL})'
            ))

        role_superadmin = roles.get('superadmin')
        _, role_created = UserRole.objects.get_or_create(user=superadmin, role=role_superadmin)
        flag = '✅ Rôle superadmin assigné' if role_created else '⏭️  Rôle déjà assigné'
        self.stdout.write(f'   {flag}')

        # ── ÉTAPE 5 : Compte administrateur ───────────────────
        self.stdout.write(self.style.HTTP_INFO(
            '\n👤 Étape 5 : Création du compte administrateur...'
        ))
        admin, created = User.objects.get_or_create(
            email=self.ADMIN_EMAIL,
            defaults={
                'first_name'  : self.ADMIN_FIRST_NAME,
                'last_name'   : self.ADMIN_LAST_NAME,
                'is_staff'    : True,
                'is_superuser': False,
                'is_active'   : True,
                'status'      : 'active',
            }
        )
        if created:
            admin.set_password(self.ADMIN_PASSWORD)
            admin.save()
            self.stdout.write(self.style.SUCCESS(
                f'\n   ✅ Administrateur créé !\n'
                f'      Email    : {self.ADMIN_EMAIL}\n'
                f'      Password : {self.ADMIN_PASSWORD}\n'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\n   ⏭️  Administrateur déjà existant ({self.ADMIN_EMAIL})'
            ))

        role_admin = roles.get('administrateur')
        _, role_created = UserRole.objects.get_or_create(user=admin, role=role_admin)
        flag = '✅ Rôle administrateur assigné' if role_created else '⏭️  Rôle déjà assigné'
        self.stdout.write(f'   {flag}')

        # ── Résumé ────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('\n📊 Vérification finale :'))
        for role_name, role in roles.items():
            nb_perms = role.role_permissions.count()
            self.stdout.write(f'   {role_name:<20} → {nb_perms} permissions')

        self.stdout.write(self.style.SUCCESS('\n✅ Initialisation terminée !\n'))