import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')
django.setup()

from stock.semantic_search import SemanticSearchService
from stock.models import Medicament
import numpy as np

def test():
    query = "mes yeux avec les larmes et rouge"
    print(f"Query: {query}")
    
    # Just to trace
    model = SemanticSearchService.get_model()
    q_emb = model.encode([query])
    
    meds = Medicament.objects.all().select_related('categorie')
    print(f"Total meds: {meds.count()}")
    for m in meds:
        m_text = SemanticSearchService.get_medication_text(m)
        m_emb = model.encode([m_text])
        score = np.dot(q_emb[0], m_emb[0]) / (np.linalg.norm(q_emb[0]) * np.linalg.norm(m_emb[0]))
        if score > 0.3:
            print(f"[{score:.4f}] {m.nom} -> {m_text[:100]}...")

    results = SemanticSearchService.search(query, top_k=5)
    print("\nResults from search method:")
    for r in results:
        print(f"{r['medicament'].nom} - Score: {r['score']}")

if __name__ == '__main__':
    test()
