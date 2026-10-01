---
type: référence
statut: à jour
mise_a_jour: 2026-09-29
remplace: archives/v1/cahier_de_tests_churn_saas.md
public: évaluateurs, formateur, contributeurs
sources: tests/, notebook §15.3, .github/workflows/ci.yml
---

[← Documentation](../index.md)

# Cahier de tests

Trois niveaux de vérification, du plus rapide au plus complet. Tous les résultats cités ont été
obtenus sur ce dépôt ; les commandes permettent de les reproduire.

| Niveau | Quoi | Quand | Commande |
|---|---|---|---|
| 1. Tests unitaires | 129 tests sur données synthétiques, sans secret ni données réelles | À chaque push (CI), en local à chaque modification | `python -m pytest -q` |
| 2. Vérifications du notebook | 10 assertions sur le livrable réel (§15.3) : le notebook s'arrête si l'une échoue | À chaque `dvc repro -s certification` | `dvc repro -s certification` |
| 3. Test de fumée de l'image | Construction de l'image avec les vrais modèles, puis `/ready` | À chaque push (CI, si le secret DagsHub est configuré) | Voir [intégration continue](integration_continue.md) |

## 1. Tests unitaires par domaine

| Domaine | Fichier | Tests | Ce qui est vérifié |
|---|---|---|---|
| Versioning | [`test_versioning.py`](../../tests/test_versioning.py) | 3 | Empreinte SHA-256 et aller-retour fidèle des manifestes |
| Ingestion Bronze | [`test_bronze.py`](../../tests/test_bronze.py) | 6 | Lecture brute, écriture Bronze, entrées du manifeste |
| Nettoyage Silver | [`test_silver.py`](../../tests/test_silver.py) | 21 | Doublons, dates multi-formats, nombres en texte, normalisation des secteurs, chaîne complète |
| Gold v1 | [`test_gold.py`](../../tests/test_gold.py) | 13 | Ratios, sélection des variables, découpage, détection de fuite (AUC) et des leurres |
| Variables v2 | [`test_features.py`](../../tests/test_features.py) | 10 | Recalcul du taux d'adoption, neutralisation des retards de paiement impossibles (v2.1), construction des 20 variables |
| Suivi MLflow | [`test_tracking.py`](../../tests/test_tracking.py) | 10 | Résolution du store (local ou distant), runs, métriques, artefacts |
| Système de décision | [`test_scoring.py`](../../tests/test_scoring.py) | 18 | Perte attendue, seuil D9, priorités et rang D14/D10, actions D11, conformité D3 |
| Explicabilité | [`test_explain.py`](../../tests/test_explain.py) | 25 | Décomposition exacte, explication d'un compte, trace de la décision, 5 contrôles, attribution de dérive, **cohérence de la base de connaissance avec le code** |
| API | [`test_api.py`](../../tests/test_api.py) | 16 | Santé, disponibilité, authentification, calcul bout en bout, neutralisation des retards impossibles, taille de requête, limite de débit, métriques, explications, garde-fou de `/ready` |
| Dérive | [`test_drift.py`](../../tests/test_drift.py) | 7 | PSI et KS sur distributions identiques et décalées, bornes figées sur la référence, valeurs manquantes |
| **Total** | | **129** | |

Les tests n'utilisent jamais les données réelles ni les `.joblib` : ils construisent des données
synthétiques ou des modèles factices dont on connaît le résultat attendu. Ils tournent donc en CI
sans aucun secret.

Lancer un domaine : `python -m pytest tests/test_explain.py -v`.

## 2. Vérifications finales du notebook (§15.3)

| Vérification | Résultat au 28/09/2026 |
|---|---|
| Aucune variable interdite dans les variables du modèle | ✅ |
| Aucun leurre dans les variables | ✅ |
| Jeux d'entraînement et de test disjoints | ✅ |
| Seuil D9 calculé sans le test (hors pli) | ✅ |
| Critère D8 respecté sur le test | ✅ |
| Actions conformes à D3 (article 22) | ✅ |
| Modèle conforme à la base de connaissance (aucun contrôle bloquant) | ✅ |
| Explication exacte (décomposition du score) | ✅ |
| Artefacts présents (modèles, manifestes, métriques, export, référence d'explication) | ✅ |
| Gold v2 et son manifeste présents | ✅ |

Le notebook vérifie aussi en cours de route que l'API renvoie les mêmes scores que l'appel direct
aux modèles, qu'elle accepte une valeur manquante et une modalité inconnue, et qu'elle refuse une
requête sans clé (§10.4).

## 3. Vérifications manuelles réalisées

| Vérification | Date | Résultat |
|---|---|---|
| Construction de l'image Docker et appel de l'API avec explication | 28/09/2026 | `/ready` en 200 avec le modèle v2 ; explications servies ; réponse sans `explain` inchangée |
| `dvc status` et `dvc status -c` après exécution | 28/09/2026 | Pipeline à jour, remote synchronisé |
| Rejeu du pipeline dans un clone jetable | 24/09/2026 | Voir le [journal](../journal/actions/2.19_pipeline_et_fins_de_ligne.md) |

## Limites connues

- **Dérive mesurée sur un découpage aléatoire**, pas sur un vrai nouveau cycle : le PSI proche de 0
  entre train et test est attendu ; seuls le mécanisme et un lot volontairement dérivé (§13.1)
  prouvent la détection.
- **Seuil D9 et capacité D10 figés** : rien n'alerte automatiquement si le taux de churn réel
  dérive.
- **Les notebooks v1 (01 à 06) gardent leur propre copie de la logique** : seul `src/` est couvert
  par les tests. Le notebook de certification, lui, importe `src/`.
- **Pas de mesure d'impact** post-déploiement ([D12](../cadrage/decisions/D12.md)).

Voir aussi : [intégration continue](integration_continue.md) · [guide de démarrage](../exploitation/guide_de_demarrage.md)
