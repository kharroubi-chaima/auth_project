import hashlib
import re
import time
import threading
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from django.core.cache import cache
from .models import Medicament

_verrou_modele = threading.Lock()

SCORE_MIN        = 0.42   # Seuil général
SCORE_MIN_PROFIL = 0.45   # Seuil plus strict quand un profil patient est détecté

# ── Cache mémoire de la matrice d'embeddings ─────────────────────────────────
# Evite de reconstruire la matrice numpy à chaque requête
_matrix_lock = threading.Lock()
_matrix_cache = {
    'matrix': None,        # np.ndarray (N, 768) — la matrice complète
    'meds': None,          # list[Medicament] — les médicaments dans le même ordre
    'last_check': 0.0,     # timestamp de la dernière vérification BDD
    'last_updated': None,  # valeur max(updated_at) au moment du build
}
CACHE_TTL = 60  # secondes avant de revérifier si la BDD a changé

# ── Contextes anatomiques étendus ─────────────────────────────────────────────
CONTEXTES_MOTS_CLES = {
    'oculaire':    ['yeux', 'oeil', 'œil', 'oculaire', 'conjonctivite', 'vision'],
    'cutane':      ['peau', 'cutané', 'cutanée', 'coup de soleil', 'brûlure peau'],
    'auriculaire': ['oreille', 'otite', "mal d'oreille"],
    'urinaire':    ['urinaire', 'cystite', 'uriner', 'pipi brûle'],
    'gorge':       ['gorge', 'avaler', 'pharyngite', 'amygdales', 'enrouement'],
}

VOIES_INCOMPATIBLES = {
    'oculaire':    ['cutanée', 'auriculaire', 'inhalation'],
    'cutane':      ['ophtalmique', 'auriculaire', 'inhalation'],
    'auriculaire': ['ophtalmique', 'cutanée', 'orale', 'inhalation'],
    'urinaire':    ['ophtalmique', 'cutanée', 'auriculaire', 'inhalation'],
    'gorge':       ['ophtalmique', 'cutanée', 'auriculaire', 'inhalation'],
}

# ── Profils patient ───────────────────────────────────────────────────────────
PROFILS_PATIENT = {
    'enfant': [
        'enfant', 'bébé', 'bebe', 'nourrisson', 'pédiatrique', 'pediatrique',
        'petit', 'fils', 'fille', 'junior', 'bb',
    ],
    'adulte': ['adulte', 'senior', 'personne âgée', 'grande personne'],
}

# ── Regex dosages adultes ─────────────────────────────────────────────────────
REGEX_DOSAGES_ADULTES = [
    re.compile(r'\b1\s*0{3}\s*mg\b', re.IGNORECASE),  # 1000mg
    re.compile(r'\b1\s*g\b',         re.IGNORECASE),   # 1g
    re.compile(r'\b500\s*mg\b',      re.IGNORECASE),   # 500mg
    re.compile(r'\b400\s*mg\b',      re.IGNORECASE),   # 400mg
]


class SemanticSearchService:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            with _verrou_modele:
                if cls._model is None:
                    cls._model = SentenceTransformer(
                        'paraphrase-multilingual-mpnet-base-v2'
                    )
        return cls._model

    @classmethod
    def get_medication_text(cls, med):
        """Prépare le texte à vectoriser pour un médicament."""
        parts = [f"Nom du médicament: {med.nom}"]
        if med.dci:
            parts.append(f"Substance active: {med.dci}")
        if med.voie_administration:
            parts.append(f"Voie d'administration: {med.voie_administration}")
        if med.symptomes_cibles:
            parts.append(f"Symptômes traités: {med.symptomes_cibles}")
        if med.categorie:
            parts.append(f"Catégorie: {med.categorie.nom}")
            if med.categorie.description:
                parts.append(f"Action: {med.categorie.description}")
        if med.description:
            parts.append(f"Description générale: {med.description}")
        if med.profil_patient and med.profil_patient != 'tous':
            parts.append(f"Profil patient: {med.profil_patient}")
        return "\n".join(parts)

    @classmethod
    def detecter_contexte(cls, query_lower: str) -> str | None:
        """Détecte le contexte anatomique de la requête."""
        for contexte, mots in CONTEXTES_MOTS_CLES.items():
            if any(mot in query_lower for mot in mots):
                return contexte
        return None

    @classmethod
    def detecter_profil(cls, query_lower: str) -> str | None:
        """Détecte le profil patient (enfant / adulte) dans la requête."""
        for profil, mots in PROFILS_PATIENT.items():
            if any(mot in query_lower for mot in mots):
                return profil
        return None

    @classmethod
    def _build_matrix(cls, model):
        """
        Charge tous les médicaments, calcule les vecteurs manquants,
        et construit la matrice numpy. Enregistre le résultat dans _matrix_cache.
        """
        meds = list(Medicament.objects.all().select_related('categorie'))
        if not meds:
            _matrix_cache['matrix'] = np.empty((0, 768))
            _matrix_cache['meds'] = []
            return

        # Calcul des vecteurs manquants (batch, plus efficace)
        missed = [m for m in meds if not m.vecteur_semantique]
        if missed:
            texts = [cls.get_medication_text(m) for m in missed]
            new_embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
            for idx, m in enumerate(missed):
                m.vecteur_semantique = new_embeddings[idx].tolist()
                m.save(update_fields=['vecteur_semantique'])

        # Construction de la matrice (une seule désérialisation JSON par requête de rebuild)
        embeddings_list = [
            m.vecteur_semantique if m.vecteur_semantique else [0.0] * 768
            for m in meds
        ]
        matrix = np.array(embeddings_list, dtype=np.float32)

        # Récupérer le timestamp max updated_at pour la détection de changement
        from django.db.models import Max
        result = Medicament.objects.aggregate(ts=Max('updated_at'))
        last_updated = result['ts']

        with _matrix_lock:
            _matrix_cache['matrix']       = matrix
            _matrix_cache['meds']         = meds
            _matrix_cache['last_check']   = time.monotonic()
            _matrix_cache['last_updated'] = last_updated

        print(f"[SemanticSearch] Matrice reconstruite : {len(meds)} medicaments.")

    @classmethod
    def _get_matrix(cls, model):
        """
        Retourne (matrix, meds) depuis le cache mémoire.
        Reconstruit si le cache est vide ou périmé / invalidé.
        """
        now = time.monotonic()

        with _matrix_lock:
            matrix  = _matrix_cache['matrix']
            meds    = _matrix_cache['meds']
            last_ck = _matrix_cache['last_check']
            last_up = _matrix_cache['last_updated']

        # Cache vide → construction immédiate
        if matrix is None:
            cls._build_matrix(model)
            with _matrix_lock:
                return _matrix_cache['matrix'], _matrix_cache['meds']

        # TTL non expiré → retourner directement sans requête BDD
        if now - last_ck < CACHE_TTL:
            return matrix, meds

        # TTL expiré → vérifier si la BDD a changé (1 seule requête légère)
        from django.db.models import Max
        result = Medicament.objects.aggregate(ts=Max('updated_at'))
        current_updated = result['ts']

        if current_updated != last_up:
            # Un médicament a été modifié → on reconstruit
            cls._build_matrix(model)
        else:
            # Rien n'a changé → juste mettre à jour last_check
            with _matrix_lock:
                _matrix_cache['last_check'] = now

        with _matrix_lock:
            return _matrix_cache['matrix'], _matrix_cache['meds']

    @classmethod
    def invalidate_cache(cls):
        """Forcer la reconstruction du cache (appelé après import/modification de médicaments)."""
        with _matrix_lock:
            _matrix_cache['matrix']       = None
            _matrix_cache['meds']         = None
            _matrix_cache['last_check']   = 0.0
            _matrix_cache['last_updated'] = None
        print("[SemanticSearch] Cache memoire invalide manuellement.")

    @classmethod
    def search(cls, query: str, top_k: int = 5) -> list[dict]:
        """
        Recherche sémantique de médicaments basée sur une requête (symptômes).
        Optimisée avec :
          - Cache mémoire de la matrice d'embeddings (reconstruction uniquement si BDD a changé)
          - Cache de l'embedding de la requête (Django cache, TTL 10 min)
          - Heuristique anatomique étendue
          - Détection de profil patient avec pénalités fortes
          - Regex robuste pour les dosages adultes
          - Seuil dynamique selon le profil détecté
        """
        model = cls.get_model()

        # 1. Cache de l'embedding de la requête (Django cache)
        query_clean = query.strip().lower()
        query_hash  = hashlib.md5(query_clean.encode('utf-8')).hexdigest()
        cache_key   = f"query_embed_v4_{query_hash}"

        query_embedding = cache.get(cache_key)
        if query_embedding is None:
            query_enriched  = f"Symptômes recherchés : {query_clean}"
            query_embedding = model.encode([query_enriched])
            cache.set(cache_key, query_embedding, timeout=600)

        # 2. Récupération de la matrice depuis le cache mémoire (rapide si rien n'a changé)
        med_matrix, meds = cls._get_matrix(model)

        if len(meds) == 0:
            return []

        # 3. Calcul de la similarité cosinus (vectorisé, très rapide)
        similarities = cosine_similarity(query_embedding, med_matrix)[0]

        # 4. Détection contexte anatomique + profil patient
        contexte = cls.detecter_contexte(query_clean)
        voies_incompatibles = VOIES_INCOMPATIBLES.get(contexte, []) if contexte else []
        profil = cls.detecter_profil(query_clean)

        results = []
        for idx, score in enumerate(similarities):
            final_score = float(score)
            m = meds[idx]
            voie     = (m.voie_administration or "").lower()
            nom_desc = f"{m.nom} {m.description or ''}".lower()

            # Pénalité anatomique
            if any(v in voie for v in voies_incompatibles):
                final_score -= 0.20

            # Pénalité si voie spécialisée sans contexte correspondant
            VOIES_SPECIALISEES = ['cutanée', 'cutanee', 'ophtalmique', 'auriculaire']
            if contexte is None:
                if any(v in voie for v in VOIES_SPECIALISEES):
                    final_score -= 0.25  # Ex: Dermovate/Biafine pénalisés par défaut si recherche de fièvre/douleur sans mention de peau

            # Pénalités profil patient (enfant)
            if profil == 'enfant':
                if m.profil_patient == 'adulte':
                    final_score -= 0.50
                if any(rx.search(nom_desc) for rx in REGEX_DOSAGES_ADULTES):
                    final_score -= 0.30

            results.append({'medicament': m, 'score': final_score})

        # 5. Tri et filtrage avec seuil dynamique
        seuil = SCORE_MIN_PROFIL if profil else SCORE_MIN
        results.sort(key=lambda x: x['score'], reverse=True)
        results = [r for r in results if r['score'] >= seuil]

        return results[:top_k]