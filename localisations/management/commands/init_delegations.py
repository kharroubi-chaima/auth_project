from django.core.management.base import BaseCommand
from localisations.models import Gouvernorat, Delegation


class Command(BaseCommand):
    help = 'Initialise les délégations tunisiennes par gouvernorat'

    DELEGATIONS = {
        "Tunis": [
            "Tunis", "Bab El Bhar", "Bab Souika", "Carthage",
            "Cité El Khadra", "El Kabaria", "El Menzah", "El Omrane",
            "El Omrane Supérieur", "Ezzouhour", "Hraïria", "La Goulette",
            "La Marsa", "Le Bardo", "Le Kram", "Médina",
            "Séjoumi", "Sidi El Béchir", "Sidi Hassine"
        ],
        "Ariana": [
            "Ariana", "Ettadhamen", "Kalaat El Andalous",
            "La Soukra", "Mnihla", "Raoued", "Sidi Thabet"
        ],
        "Ben Arous": [
            "Ben Arous", "Bou Mhel El Bassatine", "El Mourouj",
            "Ezzahra", "Fouchana", "Hammam Chott", "Hammam Lif",
            "Mégrine", "Mohamedia", "Mornag", "Nouvelle Medina", "Radès"
        ],
        "Manouba": [
            "Manouba", "Den Den", "Douar Hicher", "El Battane",
            "Jedaida", "Mornaguia", "Oued Ellil", "Tebourba"
        ],
        "Nabeul": [
            "Nabeul", "Béni Khalled", "Béni Khiar", "Bouargoub",
            "Grombalia", "Hammamet", "Kelibia", "Korba",
            "Menzel Bouzelfa", "Menzel Temime", "Soliman", "Takelsa"
        ],
        "Zaghouan": [
            "Zaghouan", "Bir Mcherga", "El Fahs", "Nadhour", "Zriba"
        ],
        "Bizerte": [
            "Bizerte Nord", "Bizerte Sud", "El Alja", "Ghar El Melh",
            "Ghezala", "Joumine", "Mateur", "Menzel Bourguiba",
            "Menzel Jemil", "Ras Jebel", "Sejnane", "Tinja", "Utique"
        ],
        "Béja": [
            "Béja Nord", "Béja Sud", "Amdoun", "Goubellat",
            "Medjez El Bab", "Nefza", "Téboursouk", "Testour", "Thibar"
        ],
        "Jendouba": [
            "Jendouba", "Ain Draham", "Balta Bou Aouane", "Bou Salem",
            "Fernana", "Ghardimaou", "Oued Meliz", "Tabarka"
        ],
        "Kef": [
            "Kef Ouest", "Kef Est", "Dahmani", "Jerissa",
            "Kalaat Senan", "Kalaat Khasba", "Nebeur",
            "Sakiet Sidi Youssef", "Tajerouine"
        ],
        "Siliana": [
            "Siliana Nord", "Siliana Sud", "Bargou", "Bou Arada",
            "El Aroussa", "Gaafour", "Kesra", "Le Krib",
            "Makthar", "Rohia"
        ],
        "Sousse": [
            "Sousse Médina", "Sousse Nord", "Sousse Riadh", "Akouda",
            "Bouficha", "Enfidha", "Hergla", "Kalaa Kebira",
            "Kalaa Sghira", "Kondar", "M'saken", "Sidi Bou Ali",
            "Sidi El Heni"
        ],
        "Monastir": [
            "Monastir", "Bembla", "Beni Hassen", "Jemmal",
            "Ksar Hellal", "Ksibet El Mediouni", "Moknine",
            "Ouerdanine", "Sahline", "Sayada Lamta Bou Hajar",
            "Téboulba", "Zeramdine"
        ],
        "Mahdia": [
            "Mahdia", "Bou Merdes", "Chebba", "Cheylus",
            "El Bradaa", "El Jem", "Ksour Essef",
            "Melloulèche", "Ouled Chamekh", "Sidi Alouane"
        ],
        "Sfax": [
            "Sfax Médina", "Sfax Ouest", "Sfax Sud", "Agareb",
            "Bir Ali Ben Khalifa", "El Amra", "El Hencha", "Ghraiba",
            "Jebiniana", "Kerkenah", "Mahres", "Menzel Chaker",
            "Sakiet Eddaier", "Sakiet Ezzit", "Thyna"
        ],
        "Kairouan": [
            "Kairouan Nord", "Kairouan Sud", "Chebika", "Chrarda",
            "Hajeb El Ayoun", "Haffouz", "El Alaa",
            "Nasrallah", "Oued Haffouz", "Sbikha"
        ],
        "Kasserine": [
            "Kasserine Nord", "Kasserine Sud", "Ezzouhour", "Feriana",
            "Foussana", "Hassi El Ferid", "Hidra", "Jediliane",
            "Majel Bel Abbes", "Sbeitla", "Sbiba", "Thala"
        ],
        "Sidi Bouzid": [
            "Sidi Bouzid Ouest", "Sidi Bouzid Est", "Ben Oun",
            "Bir El Hafey", "Cebbala Ouled Asker", "Jilma",
            "Meknassy", "Menzel Bouzaiane", "Mezzouna",
            "Ouled Haffouz", "Regueb", "Souk Jedid"
        ],
        "Gabès": [
            "Gabès Médina", "Gabès Ouest", "Gabès Sud", "El Hamma",
            "El Metouia", "Ghannouch", "Mareth", "Matmata",
            "Nouvelle Matmata", "Menzel El Habib"
        ],
        "Médenine": [
            "Médenine Nord", "Médenine Sud", "Ben Gardane",
            "Beni Khedache", "Djerba Ajim", "Djerba Houmt Souk",
            "Djerba Midoun", "Sidi Makhlouf", "Zarzis"
        ],
        "Tataouine": [
            "Tataouine Nord", "Tataouine Sud", "Bir Lahmar",
            "Dehiba", "Ghomrassen", "Remada", "Smar"
        ],
        "Gafsa": [
            "Gafsa Nord", "Gafsa Sud", "Belkhir", "El Guettar",
            "El Ksar", "Mdhilla", "Metlaoui", "Moularès",
            "Om El Araies", "Redeyef", "Sidi Aïch", "Sned"
        ],
        "Tozeur": [
            "Tozeur", "Degache", "Hazoua", "Nefta", "Tamerza"
        ],
        "Kébili": [
            "Kébili Nord", "Kébili Sud", "Douz Nord",
            "Douz Sud", "Faouar", "Souk Lahad"
        ],
    }

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0
        errors = []

        for gouvernorat_nom, delegations in self.DELEGATIONS.items():
            try:
                gouvernorat = Gouvernorat.objects.get(nom=gouvernorat_nom)
            except Gouvernorat.DoesNotExist:
                errors.append(gouvernorat_nom)
                self.stdout.write(self.style.ERROR(
                    f'    Gouvernorat introuvable : {gouvernorat_nom} '
                    f'(lance init_gouvernorats d\'abord)'
                ))
                continue

            for nom in delegations:
                _, created = Delegation.objects.get_or_create(
                    nom=nom,
                    gouvernorat=gouvernorat
                )
                if created:
                    created_count += 1
                else:
                    existing_count += 1

            self.stdout.write(
                f'    {gouvernorat_nom} → {len(delegations)} délégations'
            )

        if errors:
            self.stdout.write(self.style.ERROR(
                f'\n {len(errors)} gouvernorat(s) manquant(s) : {", ".join(errors)}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n  Délégations : {created_count} créées, {existing_count} déjà existantes'
            ))