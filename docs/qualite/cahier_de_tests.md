---
type: référence
statut: à jour
mise_a_jour: 2026-10-03
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
| 1. Tests unitaires | 214 tests sur données synthétiques, sans secret ni données réelles | À chaque push (CI), en local à chaque modification | `python -m pytest -q` |
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
| Système de décision | [`test_scoring.py`](../../tests/test_scoring.py) | 22 | Perte attendue, seuil D9, priorités et rang D14/D10, filet de sécurité D14, actions D11, conformité D3 |
| Explicabilité | [`test_explain.py`](../../tests/test_explain.py) | 26 | Décomposition exacte, explication d'un compte, trace de la décision (filet D14 compris), 5 contrôles, attribution de dérive, **cohérence de la base de connaissance avec le code** |
| API | [`test_api.py`](../../tests/test_api.py) | 27 | Santé, disponibilité, authentification, service fermé sans `API_KEY`, calcul bout en bout, neutralisation des retards impossibles, validation des entrées (variable inconnue, type, bornes), taille de requête, limite de débit, métriques, explications, garde-fous de `/ready` (base de connaissance, empreinte certifiée) |
| Validation des entrées | [`test_validation.py`](../../tests/test_validation.py) | 14 | Une borne physique par variable numérique, valeurs refusées et acceptées, troncature des erreurs, aucune valeur du Gold v2 refusée |
| Dérive | [`test_drift.py`](../../tests/test_drift.py) | 7 | PSI et KS sur distributions identiques et décalées, bornes figées sur la référence, valeurs manquantes |
| Production simulée | [`test_production.py`](../../tests/test_production.py) | 14 | Lots M+1 (format brut, étiquettes vides, ancienneté + 1, baisse d'engagement, déterminisme, lot stable sans dérive et lot dérivé en alerte, relecture par la chaîne d'entraînement), scoring d'un cycle, journal des scores (traçabilité, aucune donnée par compte, rejeu d'un cycle), purge du suivi (2 cycles), cycle courant de l'exporteur |
| Mesure d'impact | [`test_mesure_impact.py`](../../tests/test_mesure_impact.py) | 16 | Tirage D12 (effectifs B et D, renforts, 150 appels, aucun compte Haute sans action, reproductibilité), suivi minimal, rapprochement (taux, écarts et intervalles, rappel réel et son déclencheur, recette D15 (b') et (c'), écarts au protocole, aucune donnée par compte), consolidation D13, complément du journal |
| Évaluation et promotion | [`test_evaluation.py`](../../tests/test_evaluation.py) | 16 | Métriques et baseline D8, critères de promotion (un par un), reproduction des métriques publiées, trois décisions (refus, champion conservé, promouvable), déclencheurs (dérive du top 5, volume, rappel réel) |
| Ré-entraînement | [`test_reentrainement.py`](../../tests/test_reentrainement.py) | 9 | Trois familles de challengers, découpage, seuil D9 hors pli, contrôles complets ou limités, ré-entraînement à l'identique sans promotion, journal des décisions en ajout |
| **Total** | | **214** | |

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
- **Porte de qualité du modèle en CI** : `scripts/evaluer_modele.py` réévalue le modèle livré
  à chaque push ; elle ne remplace pas une évaluation sur des issues réelles.
- **Mesure d'impact outillée mais jamais exécutée sur des issues réelles** ([D12](../cadrage/decisions/D12.md)) : les tests portent sur des issues fabriquées.

Voir aussi : [intégration continue](integration_continue.md) · [guide de démarrage](../exploitation/guide_de_demarrage.md)
