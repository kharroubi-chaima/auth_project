# stock/management/commands/seed_stock.py
from datetime import date, timedelta
import random
from django.core.management.base import BaseCommand
from pharmacies.models import Pharmacie
from stock.models import ATC, Categorie, Medicament, StockPharmacie, MouvementStock
from django.contrib.auth import get_user_model

User = get_user_model()


# ── Données ATC + Catégories ──────────────────────────────────────────────────

ATC_CATEGORIES = [
    {
        "atc": "A - Système digestif et métabolisme",
        "categories": [
            ("Antiacides",                    "Neutralisation acidité gastrique"),
            ("Anti-ulcéreux",                 "Traitement des ulcères"),
            ("Antispasmodiques",              "Spasmes digestifs"),
            ("Antiémétiques",                 "Nausées et vomissements"),
            ("Laxatifs",                      "Constipation"),
            ("Antidiarrhéiques",              "Diarrhées"),
            ("Antidiabétiques oraux",         "Diabète type 2"),
            ("Insulines",                     "Diabète type 1 et 2"),
            ("Vitamines",                     "Vitamines essentielles"),
            ("Minéraux et oligoéléments",     "Calcium, Fer, Magnésium, Zinc"),
            ("Compléments nutritionnels",     "Suppléments alimentaires"),
            ("Hépatoprotecteurs",             "Protection du foie"),
            ("Enzymes digestives",            "Aide à la digestion"),
        ]
    },
    {
        "atc": "B - Sang et organes hématopoïétiques",
        "categories": [
            ("Anticoagulants",                "Prévention des thromboses"),
            ("Antiagrégants plaquettaires",   "Prévention des AVC et infarctus"),
            ("Antianémiques",                 "Traitement des anémies"),
            ("Hémostatiques",                 "Arrêt des saignements"),
            ("Substituts plasmatiques",       "Remplissage vasculaire"),
        ]
    },
    {
        "atc": "C - Système cardiovasculaire",
        "categories": [
            ("Antihypertenseurs",             "Tension artérielle élevée"),
            ("Antiarythmiques",               "Troubles du rythme cardiaque"),
            ("Antiangieux",                   "Angine de poitrine"),
            ("Cardiotoniques",                "Insuffisance cardiaque"),
            ("Diurétiques",                   "Élimination rénale de l'eau"),
            ("Hypolipémiants",                "Cholestérol et triglycérides"),
            ("Vasodilatateurs",               "Dilatation des vaisseaux"),
            ("Bêtabloquants",                 "Régulation cardiaque"),
            ("Inhibiteurs calciques",         "Hypertension et angine"),
            ("IEC / Sartans",                 "Insuffisance cardiaque et HTA"),
        ]
    },
    {
        "atc": "D - Dermatologie",
        "categories": [
            ("Corticoïdes topiques",          "Inflammation cutanée"),
            ("Antifongiques cutanés",         "Mycoses de la peau"),
            ("Antibiotiques topiques",        "Infections cutanées locales"),
            ("Antiacnéiques",                 "Traitement de l'acné"),
            ("Cicatrisants",                  "Favorise la cicatrisation"),
            ("Antiseptiques cutanés",         "Désinfection des plaies"),
            ("Émollients / Hydratants",       "Sécheresse cutanée"),
            ("Antiparasitaires cutanés",      "Gale, poux"),
            ("Antipsoriasiques",              "Psoriasis"),
        ]
    },
    {
        "atc": "G - Système génito-urinaire",
        "categories": [
            ("Contraceptifs",                 "Pilules, dispositifs contraceptifs"),
            ("Antifongiques gynécologiques",  "Mycoses vaginales"),
            ("Antibiotiques urologiques",     "Infections urinaires"),
            ("Alphabloquants",                "Hypertrophie de la prostate"),
            ("Antispasmodiques urinaires",    "Vessie hyperactive"),
            ("Hormones sexuelles féminines",  "Œstrogènes, progestérone"),
            ("Hormones sexuelles masculines", "Testostérone"),
            ("Traitements infertilité",       "Stimulation ovarienne"),
        ]
    },
    {
        "atc": "H - Hormones systémiques",
        "categories": [
            ("Corticoïdes systémiques",       "Anti-inflammatoires hormonaux"),
            ("Hormones thyroïdiennes",        "Hypothyroïdie"),
            ("Antithyroïdiens",               "Hyperthyroïdie"),
            ("Hormones hypophysaires",        "Déficits hormonaux"),
        ]
    },
    {
        "atc": "J - Anti-infectieux systémiques",
        "categories": [
            ("Antibiotiques",                 "Infections bactériennes"),
            ("Antiviraux",                    "Infections virales"),
            ("Antifongiques systémiques",     "Infections fongiques profondes"),
            ("Antiparasitaires systémiques",  "Infections parasitaires"),
            ("Antituberculeux",               "Tuberculose"),
            ("Antipaludéens",                 "Paludisme"),
            ("Vaccins",                       "Prévention des maladies infectieuses"),
        ]
    },
    {
        "atc": "L - Antinéoplasiques et immunomodulateurs",
        "categories": [
            ("Chimiothérapies",                  "Traitement des cancers"),
            ("Immunosuppresseurs",               "Greffes et maladies auto-immunes"),
            ("Immunostimulants",                 "Stimulation du système immunitaire"),
            ("Thérapies ciblées",                "Anticorps monoclonaux"),
            ("Hormonothérapies anticancéreuses", "Cancers hormonodépendants"),
        ]
    },
    {
        "atc": "M - Système musculo-squelettique",
        "categories": [
            ("Anti-inflammatoires (AINS)",    "Douleurs et inflammations"),
            ("Myorelaxants",                  "Contractures musculaires"),
            ("Antigoutteux",                  "Crise de goutte"),
            ("Antiostéoporotiques",           "Prévention fractures osseuses"),
            ("Corticoïdes articulaires",      "Infiltrations articulaires"),
        ]
    },
    {
        "atc": "N - Système nerveux",
        "categories": [
            ("Analgésiques / Antalgiques",    "Douleurs légères à modérées"),
            ("Opioïdes",                      "Douleurs sévères"),
            ("Anesthésiques",                 "Anesthésie locale et générale"),
            ("Anti-épileptiques",             "Epilepsie et convulsions"),
            ("Antiparkinsoniens",             "Maladie de Parkinson"),
            ("Antidépresseurs",               "Dépression et anxiété"),
            ("Antipsychotiques",              "Schizophrénie et psychoses"),
            ("Anxiolytiques",                 "Anxiété et stress"),
            ("Hypnotiques / Sédatifs",        "Troubles du sommeil"),
            ("Antimigraineux",                "Migraines"),
            ("Médicaments Alzheimer",         "Démences et Alzheimer"),
        ]
    },
    {
        "atc": "P - Antiparasitaires",
        "categories": [
            ("Antiprotozoaires",              "Amibiase, toxoplasmose"),
            ("Anthelminthiques",              "Vers intestinaux"),
            ("Ectoparasiticides",             "Gale, poux, puces"),
        ]
    },
    {
        "atc": "R - Système respiratoire",
        "categories": [
            ("Bronchodilatateurs",            "Dilatation des bronches"),
            ("Antiasthmatiques",              "Asthme chronique"),
            ("Corticoïdes inhalés",           "Inflammation bronchique"),
            ("Antitussifs",                   "Toux sèche"),
            ("Mucolytiques / Expectorants",   "Toux grasse"),
            ("Antihistaminiques",             "Allergies respiratoires"),
            ("Décongestionnants nasaux",      "Congestion nasale"),
            ("Antirhinites",                  "Rhinite allergique"),
        ]
    },
    {
        "atc": "S - Organes sensoriels",
        "categories": [
            ("Collyres antibiotiques",        "Infections oculaires"),
            ("Antiglaucomateux",              "Glaucome"),
            ("Larmes artificielles",          "Sécheresse oculaire"),
            ("Corticoïdes ophtalmiques",      "Inflammation oculaire"),
            ("Gouttes auriculaires",          "Infections de l'oreille"),
        ]
    },
    {
        "atc": "V - Divers",
        "categories": [
            ("Antidotes",                     "Intoxications et empoisonnements"),
            ("Produits de contraste",         "Imagerie médicale"),
            ("Désinfectants hospitaliers",    "Hygiène hospitalière"),
            ("Nutrition parentérale",         "Alimentation intraveineuse"),
        ]
    },
]



# ── Médicaments ───────────────────────────────────────────────────────────────
# (nom, dci, nom_categorie, prix_achat, prix_vente, ordonnance, jours_expiration)

MEDICAMENTS = [
    ("Doliprane 500mg",    "Paracétamol",          "Analgésiques / Antalgiques",  1.200,  2.500, False, 730),
    ("Paracétamol 1g",     "Paracétamol",          "Analgésiques / Antalgiques",  1.500,  3.000, False, 730),
    ("Amoxicilline 500mg", "Amoxicilline",         "Antibiotiques",               3.500,  6.800, True,  365),
    ("Augmentin 1g",       "Amoxicilline/Clav.",   "Antibiotiques",               6.500, 12.000, True,  365),
    ("Ibuprofène 400mg",   "Ibuprofène",           "Anti-inflammatoires (AINS)",  1.800,  3.200, False, 545),
    ("Voltarène gel",      "Diclofénac",           "Anti-inflammatoires (AINS)",  3.200,  5.500, False, 545),
    ("Amlor 5mg",          "Amlodipine",           "Inhibiteurs calciques",       4.200,  8.500, True,  730),
    ("Kardégic 75mg",      "Acide acétylsal.",     "Antiagrégants plaquettaires", 1.100,  2.200, True,  730),
    ("Atorvastatine 20mg", "Atorvastatine",        "Hypolipémiants",              3.800,  7.500, True,  730),
    ("Metformine 500mg",   "Metformine",           "Antidiabétiques oraux",       2.100,  4.200, True,  730),
    ("Oméprazole 20mg",    "Oméprazole",           "Anti-ulcéreux",               1.600,  3.100, False, 545),
    ("Cétirizine 10mg",    "Cétirizine",           "Antihistaminiques",           1.500,  2.800, False, 730),
    ("Loratadine 10mg",    "Loratadine",           "Antihistaminiques",           1.200,  2.400, False, 730),
    ("Salbutamol spray",   "Salbutamol",           "Bronchodilatateurs",          4.500,  8.000, True,  365),
    ("Bétadine solution",  "Povidone iodée",       "Antiseptiques cutanés",       2.100,  4.000, False, 365),
    ("Fluconazole 150mg",  "Fluconazole",          "Antifongiques systémiques",   2.800,  5.500, True,  365),
    ("Prednisolone 5mg",   "Prednisolone",         "Corticoïdes systémiques",     2.200,  4.400, True,  545),
    ("Vitamine C 500mg",   "Acide ascorbique",     "Vitamines",                   0.900,  1.800, False, 730),
    ("Zinc 10mg",          "Zinc",                 "Minéraux et oligoéléments",   0.800,  1.600, False, 730),
    ("Magnésium 300mg",    "Magnésium",            "Minéraux et oligoéléments",   1.100,  2.200, False, 730),
]


# ── Commande ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Remplit la base avec les données stock (ATC, catégories, médicaments, stocks, mouvements)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('\n🚀 Démarrage du seed stock...\n'))

        # ── 1. ATC + Catégories ───────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('   🗂️  ATC et Catégories...'))

        cats_map       = {}   # nom_categorie → objet Categorie
        atc_crees      = 0
        atc_existant   = 0
        cats_crees     = 0
        cats_existant  = 0

        for item in ATC_CATEGORIES:
            atc_obj, created = ATC.objects.get_or_create(
                nom=item["atc"]
            )
            if created:
                atc_crees += 1
            else:
                atc_existant += 1

            for nom_cat, desc_cat in item["categories"]:
                cat_obj, created = Categorie.objects.get_or_create(
                    nom=nom_cat,
                    defaults={
                        'atc':         atc_obj,
                        'description': desc_cat,
                    }
                )
                cats_map[nom_cat] = cat_obj
                if created:
                    cats_crees += 1
                else:
                    cats_existant += 1

        self.stdout.write(self.style.SUCCESS(
            f'      ✅ ATC      : {atc_crees} créés, {atc_existant} déjà existants\n'
            f'      ✅ Catégories: {cats_crees} créées, {cats_existant} déjà existantes'
        ))

        # ── 2. Fournisseurs ───────────────────────────────────
        # (pas de modèle Fournisseur dans ce projet)

        # ── 3. Médicaments ────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO('   💊 Médicaments...'))
        meds          = []
        meds_crees    = 0
        meds_existant = 0
        meds_erreur   = 0

        for nom, dci, nom_cat, p_achat, p_vente, ordo, jours in MEDICAMENTS:
            categorie = cats_map.get(nom_cat)

            if not categorie:
                self.stdout.write(self.style.WARNING(
                    f'      ⚠️  Catégorie introuvable : "{nom_cat}" pour {nom}'
                ))
                meds_erreur += 1
                continue

            # Gérer les doublons sans supprimer (FK protégées)
            doublons = Medicament.objects.filter(nom=nom, dci=dci)
            nb = doublons.count()

            if nb > 1:
                # Garder le premier, mettre à jour ses champs uniquement
                m = doublons.first()
                Medicament.objects.filter(pk=m.pk).update(
                    categorie          = categorie,
                    prix_achat         = p_achat,
                    prix_vente         = p_vente,
                    ordonnance_requise = ordo,
                    date_expiration    = date.today() + timedelta(days=jours),
                )
                meds.append(m)
                meds_existant += 1
            elif nb == 1:
                m = doublons.first()
                Medicament.objects.filter(pk=m.pk).update(
                    categorie          = categorie,
                    prix_achat         = p_achat,
                    prix_vente         = p_vente,
                    ordonnance_requise = ordo,
                    date_expiration    = date.today() + timedelta(days=jours),
                )
                meds.append(m)
                meds_existant += 1
            else:
                m = Medicament.objects.create(
                    nom                = nom,
                    dci                = dci,
                    categorie          = categorie,
                    prix_achat         = p_achat,
                    prix_vente         = p_vente,
                    ordonnance_requise = ordo,
                    date_expiration    = date.today() + timedelta(days=jours),
                    quantite_stock     = 0,
                    seuil_alerte       = 10,
                )
                meds.append(m)
                meds_crees += 1

        self.stdout.write(self.style.SUCCESS(
            f'      ✅ {meds_crees} créés, {meds_existant} déjà existants'
            + (f', ⚠️  {meds_erreur} erreurs' if meds_erreur else '')
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
            f'\n   📊 Résumé final :\n'
            f'      ATC         : {ATC.objects.count()}\n'
            f'      Catégories  : {Categorie.objects.count()}\n'
            f'      Médicaments : {Medicament.objects.count()}\n'
            f'      Stocks      : {StockPharmacie.objects.count()}\n'
            f'      Mouvements  : {MouvementStock.objects.count()}\n'
        ))