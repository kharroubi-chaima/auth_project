# stock/management/commands/seed_stock.py
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from pharmacies.models import Pharmacie
from stock.models import Categorie, Fournisseur, Medicament, StockPharmacie, MouvementStock
from django.contrib.auth import get_user_model

User = get_user_model()


CATEGORIES = [
    ("Antibiotiques",       "Médicaments anti-infectieux"),
    ("Antalgiques",         "Contre la douleur et la fièvre"),
    ("Anti-inflammatoires", "AINS et corticoïdes"),
    ("Cardiovasculaires",   "Tension, cœur, cholestérol"),
    ("Dermatologie",        "Crèmes, pommades, antiseptiques"),
    ("Vitamines",           "Compléments et micronutriments"),
]

FOURNISSEURS = [
    ("Pharma Maghreb", "+216 71 000 001", "contact@pharmamaghreb.tn"),
    ("MedDistrib TN",  "+216 71 000 002", "info@meddistrib.tn"),
    ("SantéPlus",      "+216 71 000 003", "commandes@santeplus.tn"),
]

MEDICAMENTS = [
    # (nom, dci, cat_idx, prix_achat, prix_vente, ordo, jours_expiration)
    ("Doliprane 500mg",    "Paracétamol",        1, 1.200,  2.500, False, 730),
    ("Amoxicilline 500mg", "Amoxicilline",       0, 3.500,  6.800, True,  365),
    ("Ibuprofène 400mg",   "Ibuprofène",         2, 1.800,  3.200, False, 545),
    ("Amlor 5mg",          "Amlodipine",         3, 4.200,  8.500, True,  730),
    ("Bétadine solution",  "Povidone iodée",     4, 2.100,  4.000, False, 365),
    ("Vitamine C 500mg",   "Acide ascorbique",   5, 0.900,  1.800, False, 730),
    ("Augmentin 1g",       "Amoxicilline/Clav.", 0, 6.500, 12.000, True,  365),
    ("Voltarène gel",      "Diclofénac",         2, 3.200,  5.500, False, 545),
    ("Kardégic 75mg",      "Acide acétylsal.",   3, 1.100,  2.200, True,  730),
    ("Cétirizine 10mg",    "Cétirizine",         2, 1.500,  2.800, False, 730),
    ("Metformine 500mg",   "Metformine",         3, 2.100,  4.200, True,  730),
    ("Oméprazole 20mg",    "Oméprazole",         2, 1.600,  3.100, False, 545),
    ("Loratadine 10mg",    "Loratadine",         2, 1.200,  2.400, False, 730),
    ("Atorvastatine 20mg", "Atorvastatine",      3, 3.800,  7.500, True,  730),
    ("Salbutamol spray",   "Salbutamol",         2, 4.500,  8.000, True,  365),
    ("Zinc 10mg",          "Zinc",               5, 0.800,  1.600, False, 730),
    ("Paracétamol 1g",     "Paracétamol",        1, 1.500,  3.000, False, 730),
    ("Fluconazole 150mg",  "Fluconazole",        4, 2.800,  5.500, True,  365),
    ("Prednisolone 5mg",   "Prednisolone",       2, 2.200,  4.400, True,  545),
    ("Magnésium 300mg",    "Magnésium",          5, 1.100,  2.200, False, 730),
]


class Command(BaseCommand):
    help = 'Remplit la base avec les données stock (médicaments, stocks, mouvements)'

    def handle(self, *args, **options):

        # ── 1. Catégories ─────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('   📂 Catégories...'))
        cats          = []
        cats_crees    = 0
        cats_existant = 0
        for nom, desc in CATEGORIES:
            c, created = Categorie.objects.get_or_create(
                nom=nom,
                defaults={'description': desc}
            )
            cats.append(c)
            if created:
                cats_crees += 1
            else:
                cats_existant += 1
        self.stdout.write(self.style.SUCCESS(
            f'      ✅ {cats_crees} créées, {cats_existant} déjà existantes'
        ))

        # ── 2. Fournisseurs ───────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('   🏭 Fournisseurs...'))
        fours          = []
        fours_crees    = 0
        fours_existant = 0
        for nom, tel, email in FOURNISSEURS:
            f, created = Fournisseur.objects.get_or_create(
                nom=nom,
                defaults={'telephone': tel, 'email': email}
            )
            fours.append(f)
            if created:
                fours_crees += 1
            else:
                fours_existant += 1
        self.stdout.write(self.style.SUCCESS(
            f'      ✅ {fours_crees} créés, {fours_existant} déjà existants'
        ))

        # ── 3. Médicaments ────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('   💊 Médicaments...'))
        meds          = []
        meds_crees    = 0
        meds_existant = 0
        for nom, dci, cat_idx, p_achat, p_vente, ordo, jours in MEDICAMENTS:
            m, created = Medicament.objects.get_or_create(
                nom=nom,
                defaults={
                    'dci':                dci,
                    'categorie':          cats[cat_idx],
                    'fournisseur':        random.choice(fours),
                    'prix_achat':         p_achat,
                    'prix_vente':         p_vente,
                    'ordonnance_requise': ordo,
                    'date_expiration':    date.today() + timedelta(days=jours),
                }
            )
            meds.append(m)
            if created:
                meds_crees += 1
            else:
                meds_existant += 1
        self.stdout.write(self.style.SUCCESS(
            f'      ✅ {meds_crees} créés, {meds_existant} déjà existants'
        ))

        # ── 4. Stocks par pharmacie ───────────────────────────
        self.stdout.write(self.style.HTTP_INFO('   🏪 Stocks par pharmacie...'))
        pharmacies = list(Pharmacie.objects.filter(est_active=True))

        if not pharmacies:
            self.stdout.write(self.style.WARNING(
                '      ⚠️  Aucune pharmacie active trouvée — '
                'stocks et mouvements ignorés.\n'
                '      👉 Crée des pharmacies puis relance : '
                'python manage.py seed_stock'
            ))
            return

        stocks_crees    = 0
        stocks_existant = 0
        for pharmacie in pharmacies:
            subset = random.sample(meds, k=random.randint(8, len(meds)))
            for med in subset:
                _, created = StockPharmacie.objects.get_or_create(
                    pharmacie=pharmacie,
                    medicament=med,
                    defaults={
                        'quantite_stock': random.randint(0, 120),
                        'seuil_alerte':   random.randint(5, 20),
                    }
                )
                if created:
                    stocks_crees += 1
                else:
                    stocks_existant += 1

        self.stdout.write(self.style.SUCCESS(
            f'      ✅ {stocks_crees} créés, {stocks_existant} déjà existants '
            f'({len(pharmacies)} pharmacies)'
        ))

        # ── 5. Mouvements de stock ────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('   📦 Mouvements de stock...'))
        admin       = User.objects.filter(is_superuser=True).first()
        tous_stocks = list(StockPharmacie.objects.all())
        echantillon = random.sample(tous_stocks, k=min(50, len(tous_stocks)))
        mvt_count   = 0

        for stock in echantillon:
            # Entrée initiale
            MouvementStock.objects.create(
                stock      = stock,
                type       = 'entree',
                quantite   = random.randint(20, 60),
                motif      = 'Stock initial',
                created_by = admin,
            )
            mvt_count += 1

            # 1 à 3 sorties
            for _ in range(random.randint(1, 3)):
                max_sortie = max(1, stock.quantite_stock // 3)
                MouvementStock.objects.create(
                    stock      = stock,
                    type       = 'sortie',
                    quantite   = random.randint(1, max_sortie),
                    motif      = random.choice([
                        'Vente comptoir',
                        'Ordonnance',
                        'Livraison patient',
                    ]),
                    created_by = admin,
                )
                mvt_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'      ✅ {mvt_count} mouvements créés'
        ))

        # ── Résumé final ──────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f'\n   📊 Résumé :\n'
            f'      Catégories  : {Categorie.objects.count()}\n'
            f'      Fournisseurs: {Fournisseur.objects.count()}\n'
            f'      Médicaments : {Medicament.objects.count()}\n'
            f'      Stocks      : {StockPharmacie.objects.count()}\n'
            f'      Mouvements  : {MouvementStock.objects.count()}'
        ))