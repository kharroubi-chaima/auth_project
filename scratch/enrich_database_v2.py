import os
from datetime import date, timedelta
from stock.models import Medicament, Categorie

def get_cat(nom):
    """Récupère ou crée une catégorie par nom."""
    # Cherche d'abord par correspondance exacte (insensible à la casse)
    cat = Categorie.objects.filter(nom__iexact=nom).first()
    if cat:
        return cat
    # Cherche par correspondance partielle
    cat = Categorie.objects.filter(nom__icontains=nom).first()
    if cat:
        return cat
    # ✅ Crée la catégorie si elle n'existe pas
    cat, created = Categorie.objects.get_or_create(nom=nom, defaults={'description': nom})
    if created:
        print(f"  [CAT CREEE] {nom}")
    return cat


# ─────────────────────────────────────────────────────────────
# Données enrichies : (nom, dci, categorie_partielle, prix_achat, prix_vente,
#                      ordonnance, jours_expiration, voie_admin, symptomes_cibles)
# ─────────────────────────────────────────────────────────────
MEDICAMENTS_ENRICHIS = [

    # ── OPHTALMOLOGIE ───────────────────────────────────────────
    ("Dacudoses", "Hyaluronate de sodium", "Larmes", 3.500, 5.500, False, 730,
     "Ophtalmique",
     "yeux secs, sécheresse oculaire, sensation de sable dans les yeux, irritation oculaire, yeux qui brûlent, fatigue oculaire, port de lentilles"),

    ("Optive", "Carboxyméthylcellulose", "Larmes", 4.200, 6.500, False, 730,
     "Ophtalmique",
     "yeux secs, sécheresse oculaire, yeux irrités, brûlure oculaire, larmes artificielles, lentilles de contact"),

    ("Floxal Collyre", "Ofloxacine", "Collyres", 6.000, 9.000, True, 365,
     "Ophtalmique",
     "infection oculaire, conjonctivite bactérienne, yeux rouges, yeux qui coulent, sécrétions oculaires, œil infecté"),

    ("Chibro-Cadron", "Néomycine / Dexaméthasone", "Corticoïdes ophtalmiques", 7.500, 11.000, True, 365,
     "Ophtalmique",
     "inflammation oculaire, yeux rouges et gonflés, conjonctivite allergique, irritation sévère de l'œil"),

    ("Optrex Yeux Rouges", "Ipratropium", "Collyres", 5.000, 7.500, False, 365,
     "Ophtalmique",
     "yeux rouges, rougeur oculaire, conjonctivite légère, irritation œil, yeux injectés de sang"),

    # ── DERMATOLOGIE ────────────────────────────────────────────
    ("Biafine", "Tréthanolamine", "Cicatrisants", 4.500, 7.000, False, 730,
     "Cutanée",
     "brûlure peau, coup de soleil, brûlure superficielle, rougeur cutanée, peau brûlée, radiothérapie, érythème"),

    ("Biseptine", "Chlorhexidine / Benzalkonium", "Antiseptiques cutanés", 3.000, 4.500, False, 730,
     "Cutanée",
     "plaie, coupure, égratignure, désinfection, blessure, plaie ouverte, antisepsie cutanée"),

    ("Dexeryl", "Glycérol / Vaseline", "Émollients / Hydratants", 5.500, 8.000, False, 730,
     "Cutanée",
     "peau sèche, eczéma, peau très sèche, démangeaisons peau, prurit cutané, xérose, peau qui tire, peau rugueuse"),

    ("Dermovate", "Clobétasol", "Corticoïdes topiques", 6.000, 9.000, True, 365,
     "Cutanée",
     "eczéma sévère, psoriasis, inflammation peau, dermatite, plaques rouges, peau qui gratte, urticaire"),

    ("Fucidine Crème", "Acide fusidique", "Antibiotiques topiques", 5.000, 7.500, True, 365,
     "Cutanée",
     "infection peau, impétigo, bouton infecté, furoncle, abcès cutané, plaie infectée, rougeur et pus"),

    ("Canestene 1%", "Clotrimazole", "Antifongiques cutanés", 4.000, 6.000, False, 730,
     "Cutanée",
     "mycose peau, champignon, tinea, pied d'athlète, mycose pied, intertrigo, démangeaisons entre les orteils"),

    ("Nizoral Shampooing", "Kétoconazole", "Antifongiques cutanés", 7.000, 10.500, False, 365,
     "Cutanée",
     "pellicules, pellicules abondantes, démangeaisons cuir chevelu, champignon cuir chevelu, séborrhée"),

    # ── GASTRO-ENTÉROLOGIE ──────────────────────────────────────
    ("Maalox", "Hydroxyde d'aluminium / Magnésium", "Antiacides", 3.500, 5.000, False, 730,
     "Orale",
     "brûlure estomac, acidité, aigreurs, remontées acides, douleur estomac après manger, crampes gastriques"),

    ("Citrate de Bétaïne", "Citrate de bétaïne", "Antiacides", 2.500, 4.000, False, 730,
     "Orale",
     "ballonnements, gaz, ventre gonflé, flatulences, digestion difficile, lourdeur après repas"),

    ("Forlax", "Macrogol", "Laxatifs", 4.000, 6.000, False, 730,
     "Orale",
     "constipation, selles dures, pas de transit, difficulté à aller aux toilettes, ventre dur"),

    ("Duphalac", "Lactulose", "Laxatifs", 3.500, 5.500, False, 730,
     "Orale",
     "constipation, transit lent, selles difficiles, constipation chronique, aller aux toilettes"),

    ("Hépatothym", "Artichaut / Radis noir", "Hépatoprotecteurs", 4.500, 6.500, False, 730,
     "Orale",
     "mal au foie, digestion lente, nausées après repas gras, lourdeur foie, crise de foie"),

    # ── ORL / RESPIRATOIRE ──────────────────────────────────────
    ("Actifed Rhume", "Pseudoéphédrine / Triprolidine", "Décongestionnants", 5.500, 8.000, False, 365,
     "Orale",
     "nez bouché, congestion nasale, rhume, nez qui coule, éternuements, sinusite légère, grippe"),

    ("Pivalone Spray", "Tixocortol", "Antirhinites", 6.000, 9.000, False, 365,
     "Nasale",
     "rhinite, nez bouché chronique, congestion nasale persistante, inflammation nasale, nez bouché permanent"),

    ("Nasonex", "Mométasone", "Antirhinites", 12.000, 17.000, True, 365,
     "Nasale",
     "rhinite allergique, nez bouché, allergie saisonnière, pollens, nez qui coule en permanence, inflammation nasale"),

    ("Strepsils", "Dichlorobenzyl / Amylmétacrésol", "Maux de gorge", 3.000, 4.500, False, 730,
     "Orale",
     "mal de gorge, gorge irritée, gorge qui gratte, douleur à avaler, enrouement, voix cassée, pharyngite"),

    ("Drill Pastilles", "Biclotymol", "Maux de gorge", 2.500, 4.000, False, 730,
     "Orale",
     "maux de gorge, gorge qui gratte, irritation gorge, amygdales, douleur gorge légère, enrouement"),

    ("Mucomyst", "Acétylcystéine", "Mucolytiques / Expectorants", 4.000, 6.000, False, 365,
     "Orale",
     "toux grasse, toux productive, mucosités, expectorations, sécrétions bronchiques, bronchite"),

    ("Bronchipret", "Thym / Lierre", "Mucolytiques / Expectorants", 5.000, 7.500, False, 730,
     "Orale",
     "toux grasse, bronchite, mucus, crachat, toux avec glaires, encombrement bronchique"),

    ("Séretide 25/125", "Salmétérol / Fluticasone", "Corticoïdes inhalés", 25.000, 35.000, True, 365,
     "Inhalation",
     "asthme, crise d'asthme, essoufflement chronique, souffle court, sifflement respiratoire, BPCO"),

    # ── DOULEUR / FIÈVRE ────────────────────────────────────────
    ("Efferalgan 500mg", "Paracétamol", "Analgésiques / Antalgiques", 1.500, 2.500, False, 730,
     "Orale",
     "fièvre, mal de tête, maux de tête, migraine, douleur, courbatures, température, état grippal"),

    ("Profenid 100mg", "Kétoprofène", "Anti-inflammatoires (AINS)", 4.000, 6.500, True, 365,
     "Orale",
     "douleur articulaire, arthrose, arthrite, tendinite, lombalgie, dos qui fait mal, inflammation"),

    ("Lamaline", "Paracétamol / Opium", "Analgésiques / Antalgiques", 5.000, 8.000, True, 365,
     "Orale",
     "douleur intense, douleur forte, douleur viscérale, migraine sévère, douleur chronique"),

    ("Imigrane 50mg", "Sumatriptan", "Antimigraineux", 12.000, 18.000, True, 365,
     "Orale",
     "migraine, crise de migraine, maux de tête violents, migraine avec aura, mal de crâne intense"),

    # ── ALLERGIES ───────────────────────────────────────────────
    ("Aerius 5mg", "Desloratadine", "Antihistaminiques", 5.000, 7.500, False, 730,
     "Orale",
     "allergie, rhinite allergique, urticaire, démangeaisons, allergie au pollen, éternuements, yeux qui larmoient"),

    ("Clarityne 10mg", "Loratadine", "Antihistaminiques", 4.000, 6.000, False, 730,
     "Orale",
     "allergie saisonnière, rhinite allergique, éternuements, démangeaisons, urticaire, allergie cutanée"),

    ("Xyzall 5mg", "Lévocétirizine", "Antihistaminiques", 5.500, 8.000, False, 730,
     "Orale",
     "allergie, éternuements, démangeaisons, urticaire, conjonctivite allergique, yeux rouges allergiques"),

    # ── CARDIO-VASCULAIRE ───────────────────────────────────────
    ("Amlodipine 5mg", "Amlodipine", "Inhibiteurs calciques", 4.000, 6.500, True, 730,
     "Orale",
     "tension artérielle élevée, hypertension, HTA, pression sanguine élevée, malaise cardiaque"),

    ("Ramipril 5mg", "Ramipril", "IEC / Sartans", 3.500, 5.500, True, 730,
     "Orale",
     "hypertension, tension artérielle, insuffisance cardiaque, HTA, risque cardiovasculaire"),

    ("Bisoprolol 5mg", "Bisoprolol", "Bêtabloquants", 3.000, 5.000, True, 730,
     "Orale",
     "cœur qui bat vite, palpitations, tachycardie, hypertension, angine de poitrine, troubles du rythme"),

    # ── OREILLE ─────────────────────────────────────────────────
    ("Otipax", "Phénazone / Lidocaïne", "Gouttes auriculaires", 5.000, 7.500, False, 730,
     "Auriculaire",
     "douleur oreille, otite, mal d'oreille, oreille qui fait mal, otite externe, bouchon cérumen douloureux"),

    ("Panotile", "Ciprofloxacine", "Gouttes auriculaires", 7.000, 10.000, True, 365,
     "Auriculaire",
     "infection oreille, otite bactérienne, oreille infectée, otite externe bactérienne, sécrétions oreille"),

    # ── DIABÈTE / MÉTABOLISME ───────────────────────────────────
    ("Glucophage 850mg", "Metformine", "Antidiabétiques oraux", 2.500, 4.000, True, 730,
     "Orale",
     "diabète, glycémie élevée, diabète de type 2, sucre dans le sang, hyperglycémie"),

    ("Lantus", "Insuline glargine", "Insulines", 30.000, 45.000, True, 180,
     "Injectable",
     "diabète de type 1, diabète de type 2 insulino-requérant, hyperglycémie, glycémie incontrôlable"),

    # ── ANXIÉTÉ / SOMMEIL ───────────────────────────────────────
    ("Lexomil", "Bromazépam", "Anxiolytiques", 2.500, 4.000, True, 730,
     "Orale",
     "anxiété, stress intense, angoisse, crise de panique, nervosité excessive, tension nerveuse"),

    ("Stilnox", "Zolpidem", "Hypnotiques / Sédatifs", 3.000, 5.000, True, 365,
     "Orale",
     "insomnie, difficultés à dormir, nuit agitée, réveils nocturnes, troubles du sommeil"),

    # ── INFECTIONS URINAIRES ────────────────────────────────────
    ("Monuril", "Fosfomycine", "Antibiotiques urologiques", 8.000, 12.000, True, 365,
     "Orale",
     "infection urinaire, cystite, brûlure urinaire, envie fréquente d'uriner, douleur miction, pipi qui brûle"),

    ("Uridoz", "D-Mannose / Canneberge", "Antibiotiques urologiques", 6.000, 9.000, False, 730,
     "Orale",
     "prévention cystite, infection urinaire récidivante, brûlure urinaire légère, douleur en urinant"),

    # ── VITAMINES & SUPPLÉMENTS ─────────────────────────────────
    ("Vitamine D3 1000 UI", "Cholécalciférol", "Vitamines", 2.000, 3.500, False, 730,
     "Orale",
     "carence en vitamine D, fatigue, os fragiles, faiblesse musculaire, immunité faible, manque de soleil"),

    ("Magné B6", "Magnésium / Vitamine B6", "Minéraux et oligoéléments", 3.500, 5.500, False, 730,
     "Orale",
     "crampes, crampes musculaires, fatigue, irritabilité, stress, spasmes, manque de magnésium"),

    ("Tardyferon", "Sulfate ferreux", "Antianémiques", 3.000, 4.500, True, 730,
     "Orale",
     "anémie, fatigue intense, pâleur, manque de fer, carence en fer, essoufflement, vertiges"),
]

# ─────────────────────────────────────────────────────────────
crees = 0
mis_a_jour = 0
erreurs = []

exp_date = date.today() + timedelta(days=730)

for item in MEDICAMENTS_ENRICHIS:
    nom, dci, cat_partial, p_achat, p_vente, ordo, jours, voie, symptomes = item

    cat = get_cat(cat_partial)
    if not cat:
        erreurs.append(f"Catégorie introuvable: '{cat_partial}' pour {nom}")
        continue

    exp = date.today() + timedelta(days=jours)

    defaults = {
        'dci': dci,
        'categorie': cat,
        'prix_achat': p_achat,
        'prix_vente': p_vente,
        'ordonnance_requise': ordo,
        'date_expiration': exp,
        'description': symptomes,
        'symptomes_cibles': symptomes,
        'voie_administration': voie,
        'vecteur_semantique': None,  # Forcer recalcul
    }

    med, created = Medicament.objects.update_or_create(
        nom=nom,
        defaults=defaults
    )

    if created:
        crees += 1
        print(f"  [NOUVEAU] {nom}")
    else:
        mis_a_jour += 1
        print(f"  [MAJ] {nom}")

print(f"\nTermine: {crees} crees, {mis_a_jour} mis a jour")
if erreurs:
    print("Erreurs:")
    for e in erreurs:
        print(f"  - {e}")
else:
    print("Aucune erreur!")
