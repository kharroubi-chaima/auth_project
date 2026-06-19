import os
import sys
import django

# Configuration de Django pour accéder aux modèles
sys.path.append(r'c:\Users\ASUS\Desktop\front-dev\auth_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')
django.setup()

from stock.semantic_search import SemanticSearchService

print("Tentative de chargement du modèle IA...")
try:
    model = SemanticSearchService.get_model()
    print("Modèle chargé avec succès !")
    
    print("Test de recherche...")
    results = SemanticSearchService.search("j'ai des brulures d'estomac", top_k=1)
    print(f"Recherche réussie ! Nombre de résultats : {len(results)}")
    if results:
        print(f"Premier résultat : {results[0]['medicament'].nom}")
except Exception as e:
    print(f"Erreur lors du chargement : {str(e)}")
