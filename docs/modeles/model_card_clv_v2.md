---
type: référence
statut: à jour (modèle en service)
mise_a_jour: 2026-10-03
sources: data/model_v2/metrics_clv.json, model_manifest.json ; notebook §9.7, §9.8, §12.2 et §12.3.1
---

[← Documentation](../index.md)

# Model card — modèle de valeur vie client (CLV) v2

Fiche d'identité du modèle de régression servi par l'API (brique 2 de la
[solution](../cadrage/besoin_et_solution.md)). Elle remplace la
[model card CLV v1](../../data/model/model_card_clv.md), conservée pour l'historique.

## Détails du modèle

| | |
|---|---|
| Type | **Gradient boosting** (`HistGradientBoostingRegressor`, `learning_rate = 0,05`, `max_iter = 400`) |
| Cible | `valeur_vie_client_eur`, apprise en `log(1 + CLV)` ; prédiction retransformée en euros (bornée à 0) |
| Préparation (dans le pipeline) | One-hot des 3 catégorielles ; médiane des 17 numériques (pas de standardisation) |
| Entrées | Les 20 mêmes variables que le modèle de churn ; `churn` et `sante_compte_fin_periode` en sont absentes ([features et cible de chaque modèle](../donnees/dictionnaire.md#features-et-cible-de-chaque-modèle)) |
| Artefact | `data/model_v2/model_clv.joblib` : 1,47 Mo, versionné par DVC (hors Git, récupéré par `dvc pull`) |
| Graine | 42 |

Les deux modèles sont indépendants : la CLV n'est **jamais** une variable du modèle de churn
(énoncé §3.2), et le churn n'entre pas dans la CLV. Leurs sorties ne se rencontrent que dans le
[système de décision](systeme_de_decision.md).

Révision v2.1 : le modèle a été réentraîné sur le Gold v2.1 (retards de paiement impossibles
neutralisés en valeur manquante) et le jeu de test relu une seconde fois, de façon assumée
(notebook §6.5 et §9.3).

## Usage prévu

- **Prévu** : **ordonner** les comptes signalés par enjeu économique, via la perte attendue =
  probabilité de churn × CLV estimée ([D14](../cadrage/decisions/D14.md)).
- **C'est ce modèle qui ordonne la liste** (notebook §9.8) : parmi les comptes signalés, la variance
  du log de la CLV estimée vaut 24 fois celle du log de la probabilité, et 84 % de la liste d'appels
  est celle qu'on obtiendrait en triant par CLV seule. La définition de la CLV pèse donc autant sur
  la décision que le modèle de churn.
- **Hors périmètre** : prévoir un chiffre d'affaires au euro près ; toute décision individuelle
  fondée sur la seule CLV estimée.

## Choix du modèle (validation croisée 5 plis, entraînement seul, R² sur `log(1 + CLV)`)

| Modèle | R² (moyenne ± écart-type) | MAE (log) | Taille |
|---|---|---|---|
| Baseline (médiane) | 0,000 | 1,640 | — |
| Ridge | 0,806 ± 0,014 | 0,708 | — |
| Forêt aléatoire | 0,887 ± 0,008 | 0,536 | 62,5 Mo |
| **Gradient boosting** | **0,883 ± 0,008** | 0,545 | **1,47 Mo** |

Forêt aléatoire et gradient boosting sont **à égalité** (écart inférieur à un écart-type). À
performance égale, le gradient boosting est retenu parce qu'il est environ 40 fois plus léger :
image Docker plus petite, chargement de l'API plus rapide.

## Performance sur le jeu de test (1 000 comptes)

| Métrique | Modèle | Baseline (médiane) |
|---|---|---|
| MAE | **40 791 €** | 81 809 € |
| RMSE | 131 162 € | — |
| R² (en euros) | 0,682 | −0,102 |
| R² (en log) | **0,891** | — |
| Erreur relative médiane | **42 %** | — |
| Corrélation de rang avec la CLV réelle | **0,94** | — |

| Taille d'entreprise | Comptes | CLV médiane | Erreur relative médiane |
|---|---|---|---|
| TPE | 326 | 1 564 € | 42 % |
| PME | 396 | 13 519 € | 42 % |
| ETI | 197 | 85 481 € | 43 % |
| GE | 81 | 390 628 € | 42 % |

**Lecture.** En euros, R² et RMSE restent pénalisés par quelques comptes à plusieurs centaines de
milliers d'euros (la cible va de 300 € à 2 M€). L'erreur relative médiane, stable d'un segment à
l'autre, et la corrélation de rang de 0,94 montrent que le modèle remplit son rôle : **ordonner** les
comptes par enjeu.

## Limites connues

- Erreur relative médiane de 42 % : la valeur affichée est un ordre de grandeur, pas un montant.
- **Non expliquée** : les explications par compte portent sur la probabilité de churn, pas sur la
  CLV. Expliquer ce modèle non linéaire demanderait SHAP (`TreeExplainer`)
  ([explicabilité](../explicabilite/methode.md)).
- Un compte de très grande valeur mais de risque modéré n'entre pas dans la liste d'appels : c'est
  une conséquence du filtre [D9](../cadrage/decisions/D09.md), pas du modèle CLV ; le filet de
  sécurité de [D14](../cadrage/decisions/D14.md) lui adresse un email.
- **Définition de la cible à confirmer.** Exprimée en mois de revenu, la CLV médiane vaut 12,3 mois
  pour les comptes de 1 à 3 mois d'ancienneté, 16,4 de 4 à 12 mois, 21,8 de 13 à 24 mois et 29,5 de
  25 à 36 mois (notebook §12.3.1). Elle croît avec l'ancienneté plus vite que le revenu : elle inclut
  probablement du **revenu déjà encaissé**, alors que la décision a besoin de la valeur future
  perdue. Question posée au propriétaire de la donnée ; d'ici là, le retour sur investissement est
  présenté en seuil de rentabilité, robuste à une valeur dix fois plus faible.

## Traçabilité

| | |
|---|---|
| Métriques suivies par DVC | [`metrics_clv.json`](../../data/model_v2/metrics_clv.json) |
| Runs d'entraînement | Expérience `churn_saas_regression_clv` sur [MLflow (DagsHub)](https://dagshub.com/guillaume.saidani/churn_saas.mlflow) |

Voir aussi : [model card churn v2](model_card_churn_v2.md)
