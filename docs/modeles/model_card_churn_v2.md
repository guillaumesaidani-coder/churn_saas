---
type: référence
statut: à jour (modèle en service)
mise_a_jour: 2026-10-03
sources: data/model_v2/model_manifest.json, metrics.json, scoring_manifest.json ; notebook §8, §9, §12
---

[← Documentation](../index.md)

# Model card — modèle de churn v2

Fiche d'identité du modèle de classification servi par l'API (brique 1 de la
[solution](../cadrage/besoin_et_solution.md)). Elle remplace la
[model card v1](../../data/model/model_card.md), conservée pour l'historique.

## Détails du modèle

| | |
|---|---|
| Type | **Régression logistique** régularisée (L2), `C = 0,03`, `max_iter = 3000`, sans pondération des classes |
| Préparation (dans le pipeline) | One-hot des 3 catégorielles (modalité inconnue ignorée) ; médiane puis standardisation des 17 numériques |
| Entrées | 20 variables du Gold v2 ([dictionnaire](../donnees/dictionnaire.md)) |
| Sortie | Probabilité de churn à l'échéance ([D2](../cadrage/decisions/D02.md)) |
| Artefact | `data/model_v2/model.joblib` : pipeline complet, versionné par DVC (hors Git, récupéré par `dvc pull`) |
| Graine | 42 |
| Produit par | [Notebook de certification](../../reports/notebooks/notebook_certifiant_churn_saas.ipynb), étape DVC `certification` |

## Usage prévu

- **Prévu** : classer les comptes par risque de résiliation, pour que le
  [système de décision](systeme_de_decision.md) construise la liste mensuelle des équipes Customer
  Success. Chaque score est accompagné de son [explication](../explicabilite/lire_une_explication.md).
- **Hors périmètre** : toute action automatique sur un compte ([D3](../cadrage/decisions/D03.md)) ;
  tout autre usage que la rétention, comme évaluer un CSM ou faire du scoring commercial
  ([D6](../cadrage/decisions/D06.md)) ; tout compte hors du périmètre des données d'entraînement
  (voir les avertissements de plage de l'explication).

## Données d'entraînement et d'évaluation

| | |
|---|---|
| Jeu | Gold v2 (version v2.1), SHA-256 `0dcb0bbd659c6479569accc19cde05629fe20acfbfdc43e3194d3af9abd1f865` |
| Entraînement | 4 000 comptes (28,0 % de churn) |
| Test | 1 000 comptes (28,0 % de churn), mis de côté dès la préparation ; lu une première fois pour la v2.0, puis **une seconde fois, assumée, pour la v2.1** (notebook §9.3) |
| Découpage | Stratifié sur `churn`, graine 42, identique à la v1 |

Préparation et exclusions : [préparation des données](../donnees/preparation.md).

**Révision v2.1** : les retards de paiement impossibles (plus de retards que de mois facturés,
449 comptes) sont neutralisés en valeur manquante avant le modèle ; la correction a été décidée
sur un critère de qualité des données, pas sur le score, et le test a été relu une seconde fois
pour la mesurer (notebook §6.5 et §9.3).

## Choix du modèle (validation croisée 5 plis, entraînement seul)

| Modèle | PR-AUC (moyenne ± écart-type) | ROC-AUC |
|---|---|---|
| Baseline naïve | 0,280 | 0,500 |
| Baseline métier [D8](../cadrage/decisions/D08.md) | 0,625 ± 0,026 | 0,797 |
| **Régression logistique** | **0,783 ± 0,020** | **0,886** |
| Forêt aléatoire | 0,764 ± 0,022 | 0,876 |
| Gradient boosting | 0,755 ± 0,021 | 0,867 |

La règle de sélection était fixée à l'avance ([protocole](protocole_experimental.md)). La
régularisation retenue (`C = 0,03`, PR-AUC CV 0,785) vient d'une recherche sur grille en
validation croisée.

## Performance sur le jeu de test

| Métrique | Modèle | Baseline métier D8 |
|---|---|---|
| PR-AUC | **0,748** | 0,593 |
| ROC-AUC | **0,882** | 0,791 |
| Gain de PR-AUC | **+0,154** (critère D8 : +0,15, respecté, marge faible) | — |

| Point de fonctionnement | Rappel | Précision | Comptes signalés |
|---|---|---|---|
| **Seuil D9 = 0,2832** (calculé hors pli sur l'entraînement) | **82,5 %** | **63,1 %** | 36,6 % |
| Seuil par défaut 0,5 (non retenu) | 54,6 % | 70,8 % | — |

**Calibration** : probabilité moyenne prédite 0,276 pour un taux réel de 0,280 ; score de Brier
0,123 contre 0,202 pour la référence. Les probabilités sont fiables, ce qui légitime le calcul de
la perte attendue en euros.

**Faut-il recalibrer ?** (lot 3, 3 octobre) Non. Erreur de calibration moyenne par déciles (ECE) :
4,5 points sur le test, 1,3 point en validation croisée sur l'entraînement. L'écart le plus fort
porte sur un décile du test (30 % prédits, 44 % observés, sur 100 comptes), ce que la validation
croisée ne confirme pas. Une recalibration n'apporte rien : Brier de 0,1229 avec Platt et 0,1238
en isotonique, contre 0,1230 sans. Les probabilités brutes de la régression logistique sont
conservées ; l'ECE est suivie à chaque évaluation (`src/evaluation.py`), sans seuil.

**Valeur métier** (cycle simulé de 1 000 comptes) : les 150 priorités Hautes contiennent
**102 comptes qui allaient réellement partir** (42 attendus au hasard) et captent **82 %** de la
perte réelle (98 % au mieux).

## Facteurs appris

Plus forts coefficients (variables standardisées : effet d'une hausse d'un écart-type sur le
logit) :

| Variable | Coefficient | Lecture |
|---|---|---|
| Ancienneté | −0,782 | Comptes récents plus à risque |
| Jours depuis la dernière connexion | +0,775 | Plus de jours sans connexion, plus de risque |
| Intégrations tierces | −0,669 | Plus d'intégrations, moins de risque |
| Tickets support sur 90 jours | +0,517 | Plus de tickets, plus de risque |
| Satisfaction (CSAT) | −0,406 | Plus satisfait, moins de risque |
| Taux d'adoption des licences | −0,307 | Plus de licences utilisées, moins de risque |
| Délai moyen de réponse du support | +0,270 | Support plus lent, plus de risque |
| Retards de paiement sur 12 mois | +0,266 | Plus de retards, plus de risque |

Les 11 variables les plus influentes vont dans le sens attendu par la
[base de connaissance](../explicabilite/base_de_connaissance.md). Ce sont des **associations
apprises**, pas des causes. Résultats des contrôles : [contrôles d'explicabilité](../explicabilite/controles.md).

## Équité

Audit du rappel et de la précision par taille d'entreprise, secteur et plan : un seul segment,
Finance (rappel 70 %, IC95 de 55 % à 81 %), ne recouvre plus le rappel global (82,5 %), de peu ;
avec 16 intervalles, un tel écart est attendu par le hasard (≈ 0,8). C'est le premier point de
surveillance ; plan Business, secteur Commerce et PME restent des points de surveillance. Détail : [RGPD, éthique et équité](../donnees/rgpd_et_ethique.md).

## Limites connues

- **Un seul instantané** des comptes : le vieillissement du modèle n'a pas pu être mesuré.
- **14 comptes partis à forte perte** n'ont pas été signalés : ils ne présentent aucun signal de
  désengagement dans les données ([D15](../cadrage/decisions/D15.md)). Seules de nouvelles données
  les rendraient détectables.
- **Deux variables construites sans apport** (`taux_utilisation_fonctionnalites`,
  `taux_retard_paiement_par_mois`) : PR-AUC quasi identique sans elles (0,785 avec, 0,784 sans) ;
  signe instable pour la première ; la seconde, stable, est une fonction exacte des retards et de
  l'ancienneté, donc son coefficient ne se lit pas comme l'effet d'un retard ; retrait recommandé
  en v3.
- **Date de calcul de `derniere_connexion_jours`** à confirmer : c'est l'une des deux variables
  les plus influentes (coefficient +0,775, juste derrière l'ancienneté).
- Seuil et capacité **figés** : une dérive du taux de churn réel rendrait le seuil progressivement
  inadapté ([supervision](../exploitation/supervision.md)).

## Traçabilité et maintenance

| | |
|---|---|
| Manifeste | [`model_manifest.json`](../../data/model_v2/model_manifest.json) : variables, hyperparamètres, métriques, `gold_sha256` |
| Métriques suivies par DVC | [`metrics.json`](../../data/model_v2/metrics.json) |
| Règle de décision | [`scoring_manifest.json`](../../data/model_v2/scoring_manifest.json) |
| Référence d'explication | [`explication_reference.json`](../../data/model_v2/explication_reference.json) |
| Runs d'entraînement | Expérience `churn_saas_classification` sur [MLflow (DagsHub)](https://dagshub.com/guillaume.saidani/churn_saas.mlflow) |
| Ré-entraînement et promotion | [Runbook](../exploitation/runbook.md) |

Voir aussi : [model card CLV v2](model_card_clv_v2.md) · [système de décision](systeme_de_decision.md)
