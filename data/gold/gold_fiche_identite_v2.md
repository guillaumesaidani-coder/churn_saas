# Fiche d'identité — Gold dataset v2

Produit par `notebooks/notebook_certifiant_churn_saas.ipynb` (commit `1789677`).
Fichier : `data/gold/clients_churn_gold_v2.parquet` — SHA-256 `0dcb0bbd659c6479569accc19cde05629fe20acfbfdc43e3194d3af9abd1f865`.

## Changements par rapport à la v1
- 5 leurres exclus (jour_souscription, pays, code_datacenter, couleur_theme_interface, groupe_experimentation) : effet nul sur le churn, exclusion demandée par l'énoncé.
- 5 colonnes du catalogue exclues (prix_mensuel_par_siege_eur, fonctionnalites_incluses, sla_reponse_h, quota_stockage_go, support_dedie) : une valeur par plan.
- Imputation par la médiane déplacée dans le pipeline (ajustée sur le train) : plus de fuite train/test.
- `taux_adoption_pct` manquant recalculé (100 × actifs / sièges) au lieu d'être imputé.
- Révision v2.1 : 449 retards de paiement impossibles (plus de retards que de mois facturés) neutralisés en valeur manquante (§6.5).

## Inchangé
- Même découpage train/test que la v1 (graine 42, stratifié) : comparaison compte par compte possible.
- `sante_compte_fin_periode` conservée pour traçabilité, jamais utilisée par les modèles.

## Composition
5000 comptes, 20 features, taux de churn 28.0%.

## Features de chaque modèle
Les deux modèles (churn et CLV) lisent les mêmes 20 features :
- 3 catégorielles, encodées en one-hot (modalité inconnue ignorée) ; modalités et nombre de comptes :
  - `secteur` (8) : Commerce 905, Tech 861, Finance 769, Industrie 666, Éducation 583, Santé 568, Public 398, Inconnu 250
  - `taille_entreprise` (4) : PME 2068, TPE 1679, ETI 893, GE 360
  - `plan` (4) : Pro 1772, Starter 1367, Business 1310, Enterprise 551
- 17 numériques, imputées par la médiane du train dans le pipeline, puis standardisées pour le seul modèle de churn : `anciennete_mois`, `sieges_souscrits`, `utilisateurs_actifs`, `taux_adoption_pct`, `connexions_30j`, `heures_usage_30j`, `fonctionnalites_total`, `fonctionnalites_utilisees`, `nb_integrations`, `derniere_connexion_jours`, `tickets_support_90j`, `delai_reponse_support_h`, `csat`, `retards_paiement_12m`, `revenu_mensuel_recurrent_eur`, `taux_utilisation_fonctionnalites`, `taux_retard_paiement_par_mois`.

## Cible et classes de chaque modèle
| | Modèle de churn | Modèle de CLV |
|---|---|---|
| Cible | `churn` | `valeur_vie_client_eur` |
| Type de problème | Classification binaire | Régression |
| Classes | 0 = reste client, 1 = résilie à l'échéance | Aucune : montant continu, appris en `log(1 + CLV)` |
| Train (4000 comptes) | 2880 × 0, 1120 × 1 | Médiane 11 086,5 € |
| Test (1000 comptes) | 720 × 0, 280 × 1 | Médiane 11 601,5 € |

Colonnes présentes mais hors des modèles : `client_id`, `split`, `sante_compte_fin_periode`. Chaque cible est absente de l'autre modèle (énoncé §3.2).
