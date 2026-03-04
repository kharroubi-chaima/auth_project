# accounts/management/commands/init_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role, Permission, UserRole, RolePermission

User = get_user_model()


class Command(BaseCommand):
    help = 'Initialise les permissions, rôles, et crée le compte administrateur'

    # ─── COORDONNÉES ADMIN ────────────────────────────────────
    ADMIN_EMAIL      = 'admin@gestionpharmacie.tn'
    ADMIN_PASSWORD   = 'Admin@2026!'
    ADMIN_FIRST_NAME = 'Super'
    ADMIN_LAST_NAME  = 'Admin'

    # ─── DÉFINITION DES PERMISSIONS PAR CATÉGORIE ─────────────
    PERMISSIONS = {
        'utilisateurs': [
            'view_user',        # voir la liste des utilisateurs
            'add_user',         # créer un compte pharmacien
            'change_user',      # modifier un utilisateur
            'delete_user',      # supprimer un utilisateur
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
            'view_pharmacie',   # voir les pharmacies
            'add_pharmacie',    # créer une pharmacie
            'change_pharmacie', # modifier une pharmacie
            'delete_pharmacie', # supprimer une pharmacie
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
            'view_pharmacie_publique',  # consultation publique pharmacies
            'view_garde_publique',      # consultation publique gardes
            'view_horaire_publique',    # consultation publique horaires
        ],
    }

    # ─── PERMISSIONS PAR RÔLE ─────────────────────────────────
    ROLE_PERMISSIONS = {

        # ── Administrateur : accès total ──────────────────────
        # Peut tout faire, y compris créer des comptes pharmaciens (add_user)
        'administrateur': '__all__',

        # ── Pharmacien : gère sa pharmacie ────────────────────
        # Ne peut PAS créer d'autres utilisateurs (pas de add_user)
        # Ne peut PAS supprimer sa pharmacie (pas de delete_pharmacie)
        'pharmacien': [
            # Utilisateurs → lecture seule
            'view_user',

            # Rôles & permissions → lecture seule
            'view_role',
            'view_permission',

            # Sa pharmacie → lecture + modification (pas suppression)
            'view_pharmacie',
            'change_pharmacie',

            # Ses horaires → CRUD complet
            'view_horaire',
            'add_horaire',
            'change_horaire',
            'delete_horaire',

            # Ses gardes → lecture + création + modification
            'view_garde',
            'add_garde',
            'change_garde',

            # Jours fériés → lecture seule
            'view_jourferie',

            # Localisations → lecture seule
            'view_gouvernorat',
            'view_delegation',

            # Consultation publique
            'view_pharmacie_publique',
            'view_garde_publique',
            'view_horaire_publique',
        ],

        # ── Citoyen : consultation publique uniquement ────────
        # Peut uniquement consulter les infos publiques
        # Ne peut PAS modifier quoi que ce soit
        'citoyen': [
            'view_pharmacie_publique',
            'view_garde_publique',
            'view_horaire_publique',
        ],
    }

    def handle(self, *args, **options):

        # ── ÉTAPE 1 : Création des permissions ────────────────
        self.stdout.write(self.style.HTTP_INFO(
            '\n🔐 Étape 1 : Création des permissions...'
        ))
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

        # ── ÉTAPE 2 : Création des rôles ──────────────────────
        self.stdout.write(self.style.HTTP_INFO(
            '\n👥 Étape 2 : Création des rôles...'
        ))
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

        # Toutes les permissions à plat pour __all__
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
                _, created = RolePermission.objects.get_or_create(
                    role=role, permission=perm
                )
                if created:
                    assigned += 1
                else:
                    already += 1

            self.stdout.write(
                f'   ✅ {role_name:<20} → '
                f'{assigned} assignées, {already} déjà existantes '
                f'({len(perms_to_assign)} au total)'
            )

        # Vérification finale des assignations
        self.stdout.write(self.style.HTTP_INFO('\n   📊 Vérification :'))
        for role_name, role in roles.items():
            nb_perms = role.role_permissions.count()
            self.stdout.write(f'      {role_name:<20} → {nb_perms} permissions')

        # ── ÉTAPE 4 : Création du compte admin ────────────────
        self.stdout.write(self.style.HTTP_INFO(
            '\n👤 Étape 4 : Création du compte administrateur...'
        ))

        user, created = User.objects.get_or_create(
            email=self.ADMIN_EMAIL,
            defaults={
                'first_name'  : self.ADMIN_FIRST_NAME,
                'last_name'   : self.ADMIN_LAST_NAME,
                'is_staff'    : True,
                'is_superuser': True,
                'is_active'   : True,
                'status'      : 'active',
            }
        )

        if created:
            user.set_password(self.ADMIN_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'\n   ✅ Administrateur créé !\n'
                f'      Email    : {self.ADMIN_EMAIL}\n'
                f'      Password : {self.ADMIN_PASSWORD}\n'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\n   ⏭️  Administrateur déjà existant ({self.ADMIN_EMAIL})'
            ))

        # ── ÉTAPE 5 : Assignation rôle administrateur → admin ─
        self.stdout.write(self.style.HTTP_INFO(
            '\n🔗 Étape 5 : Assignation du rôle administrateur...'
        ))
        role_admin      = roles.get('administrateur')
        _, role_created = UserRole.objects.get_or_create(
            user=user, role=role_admin
        )
        if role_created:
            self.stdout.write(self.style.SUCCESS(
                '   ✅ Rôle administrateur assigné'
            ))
        else:
            self.stdout.write(
                '   ⏭️  Rôle déjà assigné'
            )